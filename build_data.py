"""
build_data.py — Atoll offline data build

Runs once (locally or in CI), computes everything the app needs from the
source CSVs, writes static/data/climate_data.json. main.py/store.py never
import pandas -- they just read this file at request time.

Architecture note (changed this round): insight SENTENCES are no longer
generated here. A country's JSON entry can't know ahead of time which
compare-country a visitor will pick at request time, so per-chart dynamic
insight text (which must reference the compare country when one is
selected) is generated live in store.py from the numeric trend stats this
file DOES precompute (slope, r-squared, full series, regional median).
That keeps pandas out of the request path while still letting the insight
text react to whatever's actually on the page.

7 datasets are included -- every dataset from the original notebook that
actually had a visualization built for it (temperature anomaly, sea
surface temp anomaly, rainfall anomaly, crop yield, livestock yield, power
generation, tourism arrivals). The other 4 source CSVs (environmental
taxes, GHG emissions per capita, meteorological monitoring, sea level
anomalies) were loaded in the notebook but never turned into a chart there
either, so there's no existing visualization to carry over for those.
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd

DATA_BASE_URL = (
    "https://raw.githubusercontent.com/edimaudo/Atoll/refs/heads/main/data/"
)

INDICATORS = {
    "surface_temp_anomaly": {
        "file": "Mean%20surface%20temperature%20anomalies.csv",
        "filters": {"UNIT_MEASURE": "CELSIUS", "CLIMATE_CHANGE_INDICATORS": "ST_ANOM"},
        "unit": "\u00b0C",
        "label": "Land Surface Temperature Anomaly",
        "chapter": "ocean",
        "agg": "median",
    },
    "sea_surface_temp_anomaly": {
        "file": "%20Mean%20sea%20surface%20temperature%20anomalies.csv",
        "filters": {"CLIMATE_CHANGE_INDICATORS": "SST_ANOM", "UNIT_MEASURE": "CELSIUS"},
        "unit": "\u00b0C",
        "label": "Sea Surface Temperature Anomaly",
        "chapter": "ocean",
        "agg": "median",
    },
    "rainfall_anomaly": {
        "file": "Rainfall%20anomalies.csv",
        "filters": {"CLIMATE_CHANGE_INDICATORS": "RAIN_ANOM", "UNIT_MEASURE": "MM"},
        "unit": "mm",
        "label": "Rainfall Anomaly",
        "chapter": "land",
        "agg": "median",
    },
    "crop_yield": {
        "file": "Crop%20yield%20(disaggregated).csv",
        "filters": {"AGRICULTURE_PRODUCTION_TYPE": "CROP_YIELD", "UNIT_MEASURE": "KGHA"},
        "unit": " KG/HA",
        "label": "Crop Yield",
        "chapter": "land",
        "agg": "median",
    },
    "livestock_yield": {
        "file": "Livestock%20yield%20(disaggregated).csv",
        "filters": {"AGRICULTURE_PRODUCTION_TYPE": "LVST_YIELD", "UNIT_MEASURE": "KG_AN"},
        "unit": " KG/AN",
        "label": "Livestock Yield",
        "chapter": "land",
        "agg": "median",
    },
    "power_generation": {
        "file": "Power%20generation%20(disaggregated).csv",
        "unit": " GWH",
        "label": "Total Power Generation",
        "chapter": "people",
        "agg": "sum",
        "custom_loader": True,  # multi-dimensional source; see load_power_generation()
    },
    "tourism_arrivals": {
        "file": "Tourist%20arrivals%20(disaggregated).csv",
        "filters": {"Visitor duration category": "Overnight tourists", "UNIT_MEASURE": "N"},
        "unit": "",
        "label": "Overnight Tourist Arrivals",
        "chapter": "people",
        "agg": "sum",
    },
}

CHAPTER_ORDER = ["land", "ocean", "people"]
CHAPTER_TITLES = {
    "land": "Land & Food",
    "ocean": "Ocean & Atmosphere",
    "people": "People & Economy",
}

# Facts only -- no invented classification. Population/area sourced from the
# same country reference the original app.html used.
COUNTRY_META = {
    "American Samoa":   {"code": "AS", "lat": -14.2710, "lon": -170.1320, "flag": "\U0001F1E6\U0001F1F8", "population": "43,915",    "area_km2": "199",     "custom": "Fa'a Samoa places immense importance on the extended family and chiefs."},
    "Cook Islands":     {"code": "CK", "lat": -21.2360, "lon": -159.7770, "flag": "\U0001F1E8\U0001F1F0", "population": "17,044",    "area_km2": "236",     "custom": "Tivaevae, hand-sewn patchwork quilts, are made as ceremonial gifts."},
    "Fiji":             {"code": "FJ", "lat": -17.7134, "lon": 178.0650,  "flag": "\U0001F1EB\U0001F1EF", "population": "936,376",   "area_km2": "18,274",  "custom": "The Kava ceremony, an earthy infusion from a coconut shell, centers traditional welcomes."},
    "French Polynesia": {"code": "PF", "lat": -17.6797, "lon": -149.4068, "flag": "\U0001F1F5\U0001F1EB", "population": "308,872",   "area_km2": "4,167",   "custom": "The Heiva i Tahiti is a massive annual dance and sporting festival."},
    "Guam":             {"code": "GU", "lat": 13.4443,  "lon": 144.7937,  "flag": "\U0001F1EC\U0001F1FA", "population": "172,952",   "area_km2": "544",     "custom": "The Chenchule' is a Chamorro system of mutual gifts and assistance."},
    "Kiribati":         {"code": "KI", "lat": 1.8360,   "lon": -157.3660, "flag": "\U0001F1F0\U0001F1EE", "population": "133,515",   "area_km2": "811",     "custom": "The Maneaba, a traditional meeting house, anchors village life."},
    "Marshall Islands": {"code": "MH", "lat": 7.1315,   "lon": 171.1845,  "flag": "\U0001F1F2\U0001F1ED", "population": "41,996",    "area_km2": "181",     "custom": "Kemem celebrates a child's first birthday, historically a major survival milestone."},
    "Micronesia, Federated State of": {"code": "FM", "lat": 7.4250, "lon": 150.5500, "flag": "\U0001F1EB\U0001F1F2", "population": "115,224", "area_km2": "702", "custom": "On Yap, giant stone discs called Rai are traditionally used as currency."},
    "Nauru":            {"code": "NR", "lat": -0.5228,  "lon": 166.9315,  "flag": "\U0001F1F3\U0001F1F7", "population": "12,780",    "area_km2": "21",      "custom": "Weight lifting is a revered national sport tied to traditional strength."},
    "New Caledonia":    {"code": "NC", "lat": -20.9043, "lon": 165.6180,  "flag": "\U0001F1F3\U0001F1E8", "population": "292,991",   "area_km2": "18,576",  "custom": "The Kanak custom of 'La Coutume' involves offering yams or fabric to hosts."},
    "Niue":             {"code": "NU", "lat": -19.0544, "lon": -169.8672, "flag": "\U0001F1F3\U0001F1FA", "population": "1,681",     "area_km2": "261",     "custom": "T\u0101oga Niue preserves the island's language and traditional fishing ethos."},
    "Northern Mariana Islands": {"code": "MP", "lat": 15.0979, "lon": 145.6739, "flag": "\U0001F1F2\U0001F1F5", "population": "49,796", "area_km2": "464", "custom": "Local fiestas honoring patron saints feature abundant Chamorro food."},
    "Palau":            {"code": "PW", "lat": 7.5149,   "lon": 134.5825,  "flag": "\U0001F1F5\U0001F1FC", "population": "18,058",    "area_km2": "459",     "custom": "The Bai, a men's meeting house, was traditionally built without nails."},
    "Papua New Guinea": {"code": "PG", "lat": -6.3149,  "lon": 143.9555,  "flag": "\U0001F1F5\U0001F1EC", "population": "10,329,931","area_km2": "462,840", "custom": "The Huli Wigmen grow their hair for months to craft ceremonial wigs."},
    "Pitcairn":         {"code": "PN", "lat": -25.0667, "lon": -130.1000, "flag": "\U0001F1F5\U0001F1F3", "population": "47",        "area_km2": "47",      "custom": "Culture is tied to the Bounty mutineers' legacy and the Pitkern language."},
    "Samoa":            {"code": "WS", "lat": -13.7590, "lon": -172.1046, "flag": "\U0001F1FC\U0001F1F8", "population": "225,681",   "area_km2": "2,842",   "custom": "Pe'a is the traditional male tattoo covering waist to knees."},
    "Solomon Islands":  {"code": "SB", "lat": -9.6457,  "lon": 160.1562,  "flag": "\U0001F1F8\U0001F1E7", "population": "740,425",   "area_km2": "28,400",  "custom": "Woven shell money is still used for traditional settlements and bride prices."},
    "Tokelau":          {"code": "TK", "lat": -9.2000,  "lon": -171.8480, "flag": "\U0001F1F9\U0001F1F0", "population": "1,500",     "area_km2": "10",      "custom": "The Inati system divides all resources and fish catches equally among residents."},
    "Tonga":            {"code": "TO", "lat": -21.1789, "lon": -175.1982, "flag": "\U0001F1F9\U0001F1F4", "population": "107,773",   "area_km2": "747",     "custom": "Wearing a ta'ovala, a woven mat, around the waist shows respect in formal settings."},
    "Tuvalu":           {"code": "TV", "lat": -8.5146,  "lon": 179.1940,  "flag": "\U0001F1F9\U0001F1FB", "population": "11,396",    "area_km2": "26",      "custom": "The Fatele dance is performed to the beat of a wooden box on festive occasions."},
    "Vanuatu":          {"code": "VU", "lat": -15.3767, "lon": 166.9592,  "flag": "\U0001F1FB\U0001F1FA", "population": "334,506",   "area_km2": "12,189",  "custom": "Land diving (Naghol) on Pentecost Island preceded modern bungee jumping."},
    "Wallis and Futuna": {"code": "WF", "lat": -13.7687, "lon": -177.1560, "flag": "\U0001F1FC\U0001F1EB", "population": "11,502",   "area_km2": "142",     "custom": "Traditional royalty remains influential, with ceremonial feasts and Kava central to island life."},
}


def load_and_filter(cfg: dict) -> pd.DataFrame:
    df = pd.read_csv(f"{DATA_BASE_URL}{cfg['file']}")
    if "TIME_PERIOD" in df.columns:
        df.rename(columns={"TIME_PERIOD": "Year"}, inplace=True)
    if "Pacific Island Countries and territories" in df.columns:
        df.rename(columns={"Pacific Island Countries and territories": "Country"}, inplace=True)

    mask = pd.Series(True, index=df.index)
    for col, val in cfg["filters"].items():
        mask &= df[col] == val
    df = df[mask].copy()

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["Year", "OBS_VALUE", "Country"])
    df["Year"] = df["Year"].astype(int)
    return df[["Country", "Year", "OBS_VALUE"]]


def load_power_generation() -> pd.DataFrame:
    """Power generation isn't a single value per country/year -- it's broken
    out by energy source and grid connection status. For the line-chart
    view we want one 'total generation' number per country/year, so we sum
    every energy source's GWH figure, excluding rows that are themselves
    subtotals ('Total' in the energy-source name, or the 'Total' grid
    connection status) to avoid double-counting.
    """
    df = pd.read_csv(f"{DATA_BASE_URL}{INDICATORS['power_generation']['file']}")
    df.rename(columns={"TIME_PERIOD": "Year", "Pacific Island Countries and territories": "Country"}, inplace=True)

    mask = (
        (df["UNIT_MEASURE"] == "GWH")
        & (~df["Energy source"].str.contains("Total", case=False, na=False))
        & (df["Grid connection status"] != "Total")
    )
    df = df[mask].copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["Year", "OBS_VALUE", "Country"])
    df["Year"] = df["Year"].astype(int)
    return df[["Country", "Year", "OBS_VALUE"]]


def to_series(df: pd.DataFrame, country: str, agg: str) -> dict[int, float]:
    sub = df[df["Country"] == country]
    if sub.empty:
        return {}
    grouped = sub.groupby("Year")["OBS_VALUE"].agg(agg)
    return {int(y): round(float(v), 3) for y, v in grouped.items()}


def linear_trend(years: list[int], values: list[float]) -> dict:
    """Least-squares slope over the FULL series -- not windowed averages.

    Also reports the slope as a percentage of the series' own mean
    magnitude, so trends across indicators with very different units and
    scales (degrees C vs. tourist counts) can be fairly compared later.
    """
    x = np.array(years, dtype=float)
    y = np.array(values, dtype=float)
    if len(x) < 3:
        return {"slope_per_decade": None, "r_squared": None, "relative_slope_pct": None}

    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    mean_magnitude = float(np.mean(np.abs(y)))
    relative_slope_pct = (slope * 10 / mean_magnitude * 100) if mean_magnitude > 1e-9 else None

    return {
        "slope_per_decade": round(float(slope) * 10, 4),
        "slope_per_year": float(slope),
        "intercept": float(intercept),
        "r_squared": round(r_squared, 3),
        "relative_slope_pct": round(relative_slope_pct, 2) if relative_slope_pct is not None else None,
    }


def project_to_svg(lat: float, lon: float) -> dict:
    """Simple equirectangular projection to SVG percentage coordinates for a
    static locator dot-map. Longitudes are shifted (+360 for negatives) to
    avoid the antimeridian wraparound splitting the Pacific layout in two --
    every territory here clusters within a ~110-degree band once shifted.
    """
    shifted_lon = lon + 360 if lon < 0 else lon
    lon_min, lon_max = 125, 235
    lat_min, lat_max = -30, 20

    x_pct = (shifted_lon - lon_min) / (lon_max - lon_min) * 100
    y_pct = (lat_max - lat) / (lat_max - lat_min) * 100
    return {"x_pct": round(x_pct, 2), "y_pct": round(y_pct, 2)}


def build() -> dict:
    print("Downloading and filtering source datasets...")
    filtered = {}
    for name, cfg in INDICATORS.items():
        filtered[name] = load_power_generation() if cfg.get("custom_loader") else load_and_filter(cfg)

    regional_median = {}
    for name, df in filtered.items():
        med = df.groupby("Year")["OBS_VALUE"].median()
        regional_median[name] = {int(y): round(float(v), 3) for y, v in med.items()}

    countries_out = {}
    for country, meta in COUNTRY_META.items():
        meta = {**meta, **project_to_svg(meta["lat"], meta["lon"])}
        indicators_out = {}
        for name, cfg in INDICATORS.items():
            series = to_series(filtered[name], country, cfg["agg"])
            if not series:
                continue
            years = sorted(series)
            values = [series[y] for y in years]
            median_values = [regional_median[name].get(y) for y in years]
            trend = linear_trend(years, values)

            indicators_out[name] = {
                "label": cfg["label"],
                "unit": cfg["unit"],
                "chapter": cfg["chapter"],
                "years": years,
                "values": values,
                "regional_median": median_values,
                "trend": trend,
            }

        countries_out[country] = {"meta": meta, "indicators": indicators_out}

    chapters = {
        ck: {"title": CHAPTER_TITLES[ck], "indicators": [k for k, v in INDICATORS.items() if v["chapter"] == ck]}
        for ck in CHAPTER_ORDER
    }

    # Landing-page headline stat. Deliberately reported in the metric's own
    # unit (degrees C), not as a percentage -- surface temperature anomaly
    # crosses zero and dips negative in the early record, so a percent-
    # change framing would divide by a near-zero base and produce a
    # meaningless, wildly inflated number. Absolute change is the honest
    # framing for an anomaly series.
    temp_med = regional_median["surface_temp_anomaly"]
    temp_years = sorted(temp_med)
    headline_stat = {
        "label": "Regional Median Surface Temperature Anomaly",
        "unit": "\u00b0C",
        "start_year": temp_years[0],
        "end_year": temp_years[-1],
        "start_value": temp_med[temp_years[0]],
        "end_value": temp_med[temp_years[-1]],
        "change": round(temp_med[temp_years[-1]] - temp_med[temp_years[0]], 2),
    }

    return {
        "indicator_labels": {k: v["label"] for k, v in INDICATORS.items()},
        "chapters": chapters,
        "headline_stat": headline_stat,
        "all_country_positions": {
            name: project_to_svg(m["lat"], m["lon"]) for name, m in COUNTRY_META.items()
        },
        "countries": countries_out,
    }


if __name__ == "__main__":
    data = build()
    out_path = "static/data/climate_data.json"
    with open(out_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Wrote {out_path} ({sum(len(c['indicators']) for c in data['countries'].values())} country-indicator series)")
