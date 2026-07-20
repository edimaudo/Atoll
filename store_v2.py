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


def tail_risk_insight(country: str, indicator_label: str, unit: str, tail_risk: dict) -> str:
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
