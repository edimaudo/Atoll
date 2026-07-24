"""
store_v2.py — Atoll v2 data access + insight generation

Mirrors store.py's approach (data precomputed offline, insight text
generated live at request time) for the additional v2 chart types:
product heatmaps, ranked top/bottom-10 bars, tail-risk, and Sankey.
Reuses store.py for the shared country lookup / line-chart logic --
v2 pages need both.
"""

import json
from pathlib import Path

import store  # v1's country lookup, resolve_compare, line-chart insights

BASE_DIR = Path(__file__).parent
DATA_PATH_V2 = BASE_DIR / "static" / "data" / "climate_data_v2.json"

with open(DATA_PATH_V2) as f:
    CLIMATE_DATA_V2 = json.load(f)


def get_country_v2(name: str, fallback: str = store.DEFAULT_COUNTRY) -> tuple[str, dict]:
    if name not in CLIMATE_DATA_V2["countries"]:
        name = fallback
    return name, CLIMATE_DATA_V2["countries"][name]


def _direction(slope) -> str:
    if slope is None:
        return "held steady"
    return "risen" if slope > 0 else "fallen"


def build_indicator_insight_v2(country: str, ind: dict, compare: str = "", compare_ind: dict | None = None) -> str:
    """Per-chart dynamic insight, v2: describes the TOTAL change across the
    whole recorded timeline (e.g. "risen from X to Y over 175 years, a
    total change of Z") instead of a per-decade rate. A per-decade rate
    is hard to mentally translate into "how much did this actually
    change" -- especially over a 175-year series -- so this states the
    overall before/after and total change directly instead.
    """
    years, values, median = ind["years"], ind["values"], ind["regional_median"]
    trend = ind["trend"]
    label, unit = ind["label"], ind["unit"]

    if trend["slope_per_decade"] is None:
        return f"Data for {label.lower()} is too limited for {country} to establish a trend."

    slope_year, intercept = trend["slope_per_year"], trend["intercept"]
    fitted_start = slope_year * years[0] + intercept
    fitted_end = slope_year * years[-1] + intercept
    total_change = fitted_end - fitted_start
    span_years = years[-1] - years[0]

    parts = [
        f"Over the {span_years} years from {years[0]} to {years[-1]}, {country}'s {label.lower()} has "
        f"{_direction(trend['slope_per_decade'])} overall -- from roughly {fitted_start:.2f}{unit} to "
        f"{fitted_end:.2f}{unit}, a total change of {abs(total_change):.2f}{unit} across the whole record."
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
            comparison = (
                f"By comparison, {compare}'s most recent value is {abs(values[-1] - c_values[-1]):.2f}{unit} "
                f"{rel} {country}'s."
            )
            if c_trend["slope_per_decade"] is not None:
                c_slope_year, c_intercept = c_trend["slope_per_year"], c_trend["intercept"]
                c_total_change = (c_slope_year * c_years[-1] + c_intercept) - (c_slope_year * c_years[0] + c_intercept)
                c_span = c_years[-1] - c_years[0]
                comparison += (
                    f" Over its own {c_span}-year record, {compare} has {_direction(c_trend['slope_per_decade'])} "
                    f"by a total of {abs(c_total_change):.2f}{unit}."
                )
            parts.append(comparison)

    return " ".join(parts)


def build_action_summary_v2(country: str, country_data: dict, compare: str = "", compare_data: dict | None = None) -> str:
    """Dynamic multi-pillar Trend Summary, v2 -- same structure as before
    (one synthesized paragraph per pillar), now built on the overall-
    timeline insight sentences instead of per-decade framing.
    """
    chapters = store.CLIMATE_DATA["chapters"]
    sentences = []

    for chapter_key in ["land", "ocean", "people"]:
        chapter = chapters[chapter_key]
        chapter_lines = []
        for ind_key in chapter["indicators"]:
            ind = country_data["indicators"].get(ind_key)
            if not ind or ind["trend"]["slope_per_decade"] is None:
                continue
            compare_ind = (compare_data["indicators"].get(ind_key) if compare_data else None)
            chapter_lines.append(build_indicator_insight_v2(country, ind, compare, compare_ind))

        if chapter_lines:
            sentences.append(f"**{chapter['title']}**: " + " ".join(chapter_lines))

    return "\n\n".join(sentences)


def ranked_single_insight(country: str, indicator_label: str, unit: str, ranked_list: list, which: str) -> str:
    """Dynamic insight for a single Top-10 or Bottom-10 ranked bar chart
    (previously missing entirely -- these charts had no accompanying
    insight text at all)."""
    if not ranked_list:
        return f"Not enough product-level data is available for {country}."

    leader_name, leader_val = ranked_list[0]
    n = len(ranked_list)

    if which == "top":
        return (
            f"{leader_name} has the highest median {indicator_label.lower()} in {country} at {leader_val:.2f}{unit}, "
            f"the leading product among the top {n}."
        )
    return (
        f"{leader_name} has the lowest median {indicator_label.lower()} in {country} at {leader_val:.2f}{unit}, "
        f"the least productive of the bottom {n}."
    )


def ranked_products(country_data: dict, indicator_key: str, n: int = 10) -> dict:
    """Top-N / bottom-N products by median value across all recorded years."""
    products = country_data["products"].get(indicator_key, {})
    medians = []
    for product, series in products.items():
        if series["values"]:
            sorted_vals = sorted(series["values"])
            mid = len(sorted_vals) // 2
            median = sorted_vals[mid] if len(sorted_vals) % 2 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
            medians.append((product, median))

    medians.sort(key=lambda p: p[1], reverse=True)
    top = medians[:n]
    bottom = list(reversed(medians[-n:])) if len(medians) >= n else list(reversed(medians))
    return {"top": top, "bottom": bottom}


def ranked_products_insight(country: str, indicator_label: str, unit: str, ranked: dict) -> str:
    if not ranked["top"]:
        return f"Not enough product-level data is available for {country}."
    top_name, top_val = ranked["top"][0]
    bottom_name, bottom_val = ranked["bottom"][0]
    return (
        f"Across all recorded years, {top_name.lower()} has the highest median {indicator_label.lower()} "
        f"in {country} at {top_val:.2f}{unit}, while {bottom_name.lower()} has the lowest at {bottom_val:.2f}{unit}."
    )


def tail_risk_insight(country: str, indicator_label: str, unit: str, tail_risk: dict,
                       compare: str = "", compare_tail_risk: dict | None = None) -> str:
    n = len(tail_risk["extremes"])
    if n == 0:
        sentence = (
            f"{country} has recorded no anomalies beyond {tail_risk['threshold']:.2f}{unit} from the historical "
            f"mean ({tail_risk['mean']:.2f}{unit}) -- no extreme {indicator_label.lower()} events stand out in this record."
        )
    else:
        most_extreme = max(tail_risk["extremes"], key=lambda e: abs(e["value"] - tail_risk["mean"]))
        sentence = (
            f"{country} has recorded {n} extreme {indicator_label.lower()} event(s), each more than "
            f"{tail_risk['threshold']:.2f}{unit} from the historical mean ({tail_risk['mean']:.2f}{unit}). "
            f"The most extreme was {most_extreme['year']}, at {most_extreme['value']:.2f}{unit}."
        )

    if compare and compare_tail_risk:
        c_n = len(compare_tail_risk["extremes"])
        if c_n == 0:
            sentence += (
                f" By comparison, {compare} has recorded no anomalies beyond its own threshold of "
                f"{compare_tail_risk['threshold']:.2f}{unit} from its historical mean ({compare_tail_risk['mean']:.2f}{unit})."
            )
        else:
            c_most_extreme = max(compare_tail_risk["extremes"], key=lambda e: abs(e["value"] - compare_tail_risk["mean"]))
            sentence += (
                f" By comparison, {compare} has recorded {c_n} extreme event(s) of its own, the most extreme "
                f"being {c_most_extreme['year']} at {c_most_extreme['value']:.2f}{unit}."
            )

    return sentence


def power_source_insight(country: str, power_sources: dict) -> str:
    if not power_sources:
        return f"No power generation source data is available for {country}."

    latest_year = max(max(s["years"]) for s in power_sources.values() if s["years"])
    latest_mix = {
        name: s["values"][s["years"].index(latest_year)]
        for name, s in power_sources.items()
        if latest_year in s["years"]
    }
    if not latest_mix:
        return f"No power generation source data is available for {country} in the most recent year."

    top_source = max(latest_mix, key=latest_mix.get)
    total = sum(latest_mix.values())
    return (
        f"As of {latest_year}, {country}'s power generation was led by {top_source.lower()}, "
        f"contributing {latest_mix[top_source]:.1f} GWH of {total:.1f} GWH total that year."
    )


def sankey_insight(country: str, sankey: dict) -> str:
    links = sankey["links"]
    if not links:
        return f"No power generation flow data is available for {country}."
    total = sum(l["value"] for l in links)
    on_grid = [l for l in links if l["target"] == "On-grid"]
    off_grid = [l for l in links if l["target"] == "Off-grid"]
    top_on = max(on_grid, key=lambda l: l["value"]) if on_grid else None
    top_off = max(off_grid, key=lambda l: l["value"]) if off_grid else None

    parts = [f"Across the recorded period, {country} generated {total:.1f} GWH in total."]
    if top_on:
        parts.append(f"{top_on['source']} leads On-grid supply at {top_on['value']:.1f} GWH.")
    if top_off:
        parts.append(f"{top_off['source']} leads Off-grid supply at {top_off['value']:.1f} GWH.")
    return " ".join(parts)
