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
    """Validate a compare-country selection."""
    if not compare or compare == primary or compare not in CLIMATE_DATA["countries"]:
        return ""
    return compare


def build_chart_payload(country: str, country_data: dict, compare: str) -> dict:
    """Client-side chart payload mapped dynamically including newly merged sub-datasets."""
    payload = {
        "primary": {"name": country, **country_data},
        "compare": None
    }
    
    if compare:
        payload["compare"] = {"name": compare, **CLIMATE_DATA["countries"][compare]}
        
    return payload


def _direction(change_val) -> str:
    if change_val is None:
        return "held steady"
    # Treat very small floating changes effectively as zero for narrative purposes
    if abs(change_val) < 1e-4:
        return "held steady"
    return "risen" if change_val > 0 else "fallen"


def build_indicator_insight(country: str, ind: dict, compare: str = "", compare_ind: dict | None = None) -> str:
    """
    Per-chart dynamic insight evaluating total change over the entire historical 
    timeline (instead of per-decade steps).
    """
    years, values, median = ind["years"], ind["values"], ind["regional_median"]
    trend = ind["trend"]
    label, unit = ind["label"], ind["unit"]

    if trend.get("slope_per_year") is None:
        return f"Data for {label.lower()} is too limited for {country} to establish a trend."

    slope_year, intercept = trend["slope_per_year"], trend["intercept"]
    fitted_start = slope_year * years[0] + intercept
    fitted_end = slope_year * years[-1] + intercept
    total_change = fitted_end - fitted_start

    parts = [
        f"From {years[0]} to {years[-1]}, {country}'s {label.lower()} has {_direction(total_change)} "
        f"by an estimated {abs(total_change):.2f}{unit} over the recorded period, moving from roughly "
        f"{fitted_start:.2f}{unit} to {fitted_end:.2f}{unit} along its trendline."
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
        if c_years and c_values and c_trend.get("slope_per_year") is not None:
            c_fitted_start = c_trend["slope_per_year"] * c_years[0] + c_trend["intercept"]
            c_fitted_end = c_trend["slope_per_year"] * c_years[-1] + c_trend["intercept"]
            c_total_change = c_fitted_end - c_fitted_start
            
            rel = "higher than" if values[-1] > c_values[-1] else ("lower than" if values[-1] < c_values[-1] else "the same as")
            parts.append(
                f"By comparison, {compare}'s most recent value is {abs(values[-1] - c_values[-1]):.2f}{unit} "
                f"{rel} {country}'s, and has {_direction(c_total_change)} over its own recorded period."
            )

    return " ".join(parts)


def build_action_summary(country: str, country_data: dict, compare: str = "", compare_data: dict | None = None) -> str:
    """Dynamic multi-pillar summary using the overall timeline trend."""
    chapters = CLIMATE_DATA["chapters"]
    sentences = []

    for chapter_key in ["land", "ocean", "people"]:
        chapter = chapters[chapter_key]
        chapter_lines = []
        for ind_key in chapter["indicators"]:
            ind = country_data["indicators"].get(ind_key)
            if not ind or ind["trend"].get("slope_per_year") is None:
                continue
            compare_ind = (compare_data["indicators"].get(ind_key) if compare_data else None)
            chapter_lines.append(build_indicator_insight(country, ind, compare, compare_ind))

        if chapter_lines:
            sentences.append(f"**{chapter['title']}**: " + " ".join(chapter_lines))

    return "\n\n".join(sentences)


def ranked_products(country_data: dict, indicator_key: str, n: int = 10) -> dict:
    products = country_data.get("products", {}).get(indicator_key, {})
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


def tail_risk_insight(country: str, indicator_label: str, unit: str, tail_risk: dict) -> str:
    if not tail_risk:
        return f"No tail risk data available for {country}."
    n = len(tail_risk["extremes"])
    if n == 0:
        return (
            f"{country} has recorded no anomalies beyond {tail_risk['threshold']:.2f}{unit} from the historical "
            f"mean ({tail_risk['mean']:.2f}{unit}) -- no extreme {indicator_label.lower()} events stand out in this record."
        )
    most_extreme = max(tail_risk["extremes"], key=lambda e: abs(e["value"] - tail_risk["mean"]))
    return (
        f"{country} has recorded {n} extreme {indicator_label.lower()} event(s), each more than "
        f"{tail_risk['threshold']:.2f}{unit} from the historical mean ({tail_risk['mean']:.2f}{unit}). "
        f"The most extreme was {most_extreme['year']}, at {most_extreme['value']:.2f}{unit}."
    )


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
    links = sankey.get("links", [])
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
