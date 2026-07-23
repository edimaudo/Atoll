"""
build_data_v2.py — Atoll v2 data build (additive)

Runs AFTER build_data.py. Reads static/data/climate_data.json (v1's output)
and adds the extra chart data v2 needs on top of it: product-level crop/
livestock breakdowns (for heatmaps + ranked top/bottom-10 bars), power
generation by energy source (heatmap) and by source+grid-connection
(Sankey), and tail-risk statistics (temperature + rainfall extreme
events). Writes static/data/climate_data_v2.json as a standalone file --
v1 and v2 are separate artifacts, so /app (v1) is unaffected by any of this.

Reuses build_data.py's loaders/country metadata rather than duplicating them.
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd

from build_data import DATA_BASE_URL, COUNTRY_META, linear_trend

PRODUCT_DATASETS = {
    "crop_yield": {
        "file": "Crop%20yield%20(disaggregated).csv",
        "filters": {"AGRICULTURE_PRODUCTION_TYPE": "CROP_YIELD", "UNIT_MEASURE": "KGHA"},
        "unit": " KG/HA",
        "label": "Crop Yield",
    },
    "livestock_yield": {
        "file": "Livestock%20yield%20(disaggregated).csv",
        "filters": {"AGRICULTURE_PRODUCTION_TYPE": "LVST_YIELD", "UNIT_MEASURE": "KG_AN"},
        "unit": " KG/AN",
        "label": "Livestock Yield",
    },
}

TAIL_RISK_INDICATORS = ["surface_temp_anomaly", "rainfall_anomaly"]


def load_product_data(cfg: dict) -> pd.DataFrame:
    df = pd.read_csv(f"{DATA_BASE_URL}{cfg['file']}")
    df.rename(columns={
        "TIME_PERIOD": "Year",
        "Pacific Island Countries and territories": "Country",
    }, inplace=True)

    mask = pd.Series(True, index=df.index)
    for col, val in cfg["filters"].items():
        mask &= df[col] == val
    df = df[mask].copy()

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["Year", "OBS_VALUE", "Country", "Agricultural product"])
    df["Year"] = df["Year"].astype(int)
    return df[["Country", "Year", "Agricultural product", "OBS_VALUE"]]


def load_power_by_source() -> pd.DataFrame:
    """Per-source generation (Grid connection status == Total, to avoid
    double-counting on-grid + off-grid), for the source x year heatmap."""
    df = pd.read_csv(f"{DATA_BASE_URL}Power%20generation%20(disaggregated).csv")
    df.rename(columns={"TIME_PERIOD": "Year", "Pacific Island Countries and territories": "Country"}, inplace=True)
    mask = (
        (df["UNIT_MEASURE"] == "GWH")
        & (~df["Energy source"].str.contains("Total", case=False, na=False))
        & (df["Grid connection status"] == "Total")
    )
    df = df[mask].copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["Year", "OBS_VALUE", "Country", "Energy source"])
    df["Year"] = df["Year"].astype(int)
    return df[["Country", "Year", "Energy source", "OBS_VALUE"]]


def load_power_by_source_and_grid() -> pd.DataFrame:
    """Source x grid-connection totals (On-grid / Off-grid only, summed
    across all years), for the Sankey diagram.

    Excludes energy-source subtotal rows ("Renewable (total)", "Non-
    renewable (total)") -- without this filter they'd double-count
    generation already broken out by individual source (Oil, Solar, etc).
    The original notebook's Sankey cell didn't apply this filter; fixing
    it here rather than carrying the double-count forward.
    """
    df = pd.read_csv(f"{DATA_BASE_URL}Power%20generation%20(disaggregated).csv")
    df.rename(columns={"TIME_PERIOD": "Year", "Pacific Island Countries and territories": "Country"}, inplace=True)
    mask = (
        (df["UNIT_MEASURE"] == "GWH")
        & (df["Grid connection status"].isin(["Off-grid", "On-grid"]))
        & (~df["Energy source"].str.contains("total", case=False, na=False))
    )
    df = df[mask].copy()
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE", "Country", "Energy source", "Grid connection status"])
    return df[["Country", "Energy source", "Grid connection status", "OBS_VALUE"]]


def build_product_json(df: pd.DataFrame, country: str) -> dict:
    """{product: {years: [...], values: [...]}} for one country, sorted by
    each product's median value descending (so ranked bars are trivial to
    read straight off this structure)."""
    sub = df[df["Country"] == country]
    out = {}
    for product, grp in sub.groupby("Agricultural product"):
        grp = grp.groupby("Year")["OBS_VALUE"].median().sort_index()
        if grp.empty:
            continue
        out[product] = {"years": [int(y) for y in grp.index], "values": [round(float(v), 2) for v in grp.values]}
    return out


def build_power_source_json(df: pd.DataFrame, country: str) -> dict:
    sub = df[df["Country"] == country]
    out = {}
    for source, grp in sub.groupby("Energy source"):
        grp = grp.groupby("Year")["OBS_VALUE"].sum().sort_index()
        if grp.empty:
            continue
        out[source] = {"years": [int(y) for y in grp.index], "values": [round(float(v), 2) for v in grp.values]}
    return out


def build_sankey_json(df: pd.DataFrame, country: str) -> dict:
    sub = df[df["Country"] == country]
    agg = sub.groupby(["Energy source", "Grid connection status"])["OBS_VALUE"].sum().reset_index()
    return {
        "links": [
            {"source": row["Energy source"], "target": row["Grid connection status"], "value": round(float(row["OBS_VALUE"]), 2)}
            for _, row in agg.iterrows()
        ]
    }


def build_tail_risk(years: list[int], values: list[float]) -> dict:
    """+/-2 standard deviation extreme-event analysis -- mirrors the
    notebook's tail-risk cells for temperature and rainfall."""
    arr = np.array(values, dtype=float)
    mean_val = float(arr.mean())
    std_val = float(arr.std())
    threshold = 2 * std_val

    extremes = [
        {"year": y, "value": v}
        for y, v in zip(years, values)
        if abs(v - mean_val) > threshold
    ]

    return {
        "years": years,
        "values": values,
        "mean": round(mean_val, 3),
        "std": round(std_val, 3),
        "threshold": round(threshold, 3),
        "extremes": extremes,
    }


def build() -> dict:
    with open("static/data/climate_data.json") as f:
        v1 = json.load(f)

    print("Downloading product-level and power-source datasets...")
    product_dfs = {name: load_product_data(cfg) for name, cfg in PRODUCT_DATASETS.items()}
    power_source_df = load_power_by_source()
    power_sankey_df = load_power_by_source_and_grid()

    for country in COUNTRY_META:
        country_data = v1["countries"][country]

        country_data["products"] = {
            name: build_product_json(df, country) for name, df in product_dfs.items()
        }
        country_data["power_sources"] = build_power_source_json(power_source_df, country)
        country_data["power_sankey"] = build_sankey_json(power_sankey_df, country)

        tail_risk = {}
        for ind_key in TAIL_RISK_INDICATORS:
            ind = country_data["indicators"].get(ind_key)
            if ind and ind["years"]:
                tail_risk[ind_key] = build_tail_risk(ind["years"], ind["values"])
        country_data["tail_risk"] = tail_risk

    return v1


if __name__ == "__main__":
    data = build()
    out_path = "static/data/climate_data_v2.json"
    with open(out_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Wrote {out_path}")
