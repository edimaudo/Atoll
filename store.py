"""
store.py — Atoll data access + request-time insight generation

Owns reading the pre-built static/data/climate_data.json, exposing lookups,
and generating the natural-language "dynamic insight" text that accompanies
every chart. That text generation happens HERE (at request time) rather
than in build_data.py, because it has to react to whichever compare-country
a visitor picks in the browser -- a country's JSON entry can't know that in
advance. This is cheap arithmetic/string formatting on numbers that are
already computed, so it doesn't reintroduce any pandas/heavy-compute cost
to the request path.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "static" / "data" / "climate_data.json"
DEFAULT_COUNTRY = "Fiji"

with open(DATA_PATH) as f:
    CLIMATE_DATA = json.load(f)

COUNTRY_NAMES = sorted(CLIMATE_DATA["countries"].keys())


def get_country(name: str, fallback: str = DEFAULT_COUNTRY) -> tuple[str, dict]:
    """Look up a country's data, falling back to a default if the name is unknown."""
    if name not in CLIMATE_DATA["countries"]:
        name = fallback
    return name, CLIMATE_DATA["countries"][name]


def resolve_compare(primary: str, compare: str) -> str:
    """Validate a compare-country selection. Unknown names, empty strings,
    and picking the same country you're already viewing all resolve to "no
    compare selected" -- this rule applies uniformly across every chart
    type (line, tail-risk, heatmap, ranked bars, Sankey), not just some.
    """
    if not compare or compare == primary or compare not in CLIMATE_DATA["countries"]:
        return ""
    return compare


def build_chart_payload(country: str, country_data: dict, compare: str) -> dict:
    """Client-side chart payload -- only ships the 1-2 countries this page
    actually needs, not the whole dataset."""
    return {
        "primary": {"name": country, **country_data},
        "compare": (
            {"name": compare, **CLIMATE_DATA["countries"][compare]}
            if compare else None
        ),
    }


def _direction(slope) -> str:
    if slope is None:
        return "held steady"
    return "risen" if slope > 0 else "fallen"


def build_indicator_insight(country: str, ind: dict, compare: str = "", compare_ind: dict | None = None) -> str:
    """Per-chart dynamic insight -- mirrors the notebook's "Dynamic Insight
    for {country}" pattern: own trend, comparison to the regional median,
    and (new) comparison to the compare country when one is selected.
    """
    years, values, median = ind["years"], ind["values"], ind["regional_median"]
    trend = ind["trend"]
    label, unit = ind["label"], ind["unit"]

    if trend["slope_per_decade"] is None:
        return f"Data for {label.lower()} is too limited for {country} to establish a trend."

    slope_year, intercept = trend["slope_per_year"], trend["intercept"]
    fitted_start = slope_year * years[0] + intercept
    fitted_end = slope_year * years[-1] + intercept

    parts = [
        f"From {years[0]} to {years[-1]}, {country}'s {label.lower()} has {_direction(trend['slope_per_decade'])} "
        f"at a rate of {abs(trend['slope_per_decade']):.2f}{unit} per decade, from roughly {fitted_start:.2f}{unit} "
        f"to {fitted_end:.2f}{unit} along that trend."
    ]

    if median and median[-1] is not None:
        last_val, last_med = values[-1], median[-1]
        if abs(last_val - last_med) < 1e-6:
            parts.append(f"That's in line with the regional median of {last_med:.2f}{unit}.")
        else:
            rel = "above" if last_val > last_med else "below"
            parts.append(f"That's {abs(last_val - last_med):.2f}{unit} {rel} the regional median ({last_med:.2f}{unit}).")

    if compare and compare_ind and compare_ind.get("values"):
        c_years, c_values = compare_ind["years"], compare_ind["values"]
        c_trend = compare_ind["trend"]
        if c_years and c_values:
            rel = "higher than" if values[-1] > c_values[-1] else ("lower than" if values[-1] < c_values[-1] else "the same as")
            parts.append(
                f"By comparison, {compare}'s most recent value is {abs(values[-1] - c_values[-1]):.2f}{unit} "
                f"{rel} {country}'s, and has {_direction(c_trend['slope_per_decade'])} over its own recorded period."
            )

    return " ".join(parts)


def build_action_summary(country: str, country_data: dict, compare: str = "", compare_data: dict | None = None) -> str:
    """Dynamic multi-pillar summary for the Action Steps section -- the
    synthesis-across-indicators text lives here now, not attached to each
    pillar section. Compare-aware: extends to a three-way read (country,
    regional median, compare country) when a compare country is selected.
    """
    chapters = CLIMATE_DATA["chapters"]
    sentences = []

    for chapter_key in ["land", "ocean", "people"]:
        chapter = chapters[chapter_key]
        chapter_lines = []
        for ind_key in chapter["indicators"]:
            ind = country_data["indicators"].get(ind_key)
            if not ind or ind["trend"]["slope_per_decade"] is None:
                continue
            compare_ind = (compare_data["indicators"].get(ind_key) if compare_data else None)
            chapter_lines.append(build_indicator_insight(country, ind, compare, compare_ind))

        if chapter_lines:
            sentences.append(f"**{chapter['title']}**: " + " ".join(chapter_lines))

    return "\n\n".join(sentences)
