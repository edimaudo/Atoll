"""
Pacific Data Viz 2026
=====================

Refactored from `Pacific_Data_Viz_2026.ipynb` into a single script.

The notebook contained ~70 cells covering 11 Pacific climate/economic
datasets. Almost every section repeated the same four-step recipe:

    1. filter the raw dataframe + rename OBS_VALUE -> a friendly column name
    2. aggregate to one value per Country/Year (median)
    3. build a "country vs. regional median" line chart with custom hover text
    4. generate a templated markdown "dynamic insight" paragraph

A few sections repeat two other recipes: a top/bottom-10 bar chart, and a
product x year heatmap. One section (power generation) also builds a Sankey
diagram, and two sections (temperature, rainfall) run a "tail risk" analysis
(values more than 2 standard deviations from the mean).

Rather than pasting all 70 cells one after another, this script factors each
recipe into a single reusable function and calls it once per dataset. This
cuts the ~2500 lines of near-duplicate notebook code down to a few hundred
lines of shared logic plus a short, readable "recipe" per section.

Note: `sklearn.cluster.KMeans`, `sklearn.preprocessing.StandardScaler`, and
`statsmodels.tsa.stattools.grangercausalitytests`/`xgboost` were imported in
the original notebook but never used anywhere in its 70 cells, so they are
dropped here. `environmental_taxes_df`, `greenhouse_gas_emissions_df`, and
`meteorological_monitoring_df` are loaded and cleaned (for the shared
country list) but were likewise never visualized in the notebook; they are
kept here for the same reason, ready for a future section to use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import IPython.display as ipd


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

DATA_BASE_URL = (
    "https://raw.githubusercontent.com/edimaudo/Atoll/refs/heads/main/data/"
)

DATA_FILES = {
    "mean_surface_temp_anomalies": "Mean%20surface%20temperature%20anomalies.csv",
    "mean_sea_surface_temp_anomalies": "%20Mean%20sea%20surface%20temperature%20anomalies.csv",
    "crop_yield": "Crop%20yield%20(disaggregated).csv",
    "environmental_taxes": "Environmental%20taxes%20(disaggregated).csv",
    "greenhouse_gas_emissions": "Greenhouse%20gas%20emissions%20per%20capita.csv",
    "livestock_yield": "Livestock%20yield%20(disaggregated).csv",
    "meteorological_monitoring": "Meteorological%20monitoring%20network%20(disaggregated).csv",
    "power_generation": "Power%20generation%20(disaggregated).csv",
    "rainfall_anomalies": "Rainfall%20anomalies.csv",
    "sea_level_anomalies": "Sea%20level%20anomalies.csv",
    "tourist_arrivals": "Tourist%20arrivals%20(disaggregated).csv",
}

SELECTED_COUNTRY = "Fiji"
NUM_YEARS_FOR_TREND = 10

COLORS = {
    "temperature": ["#ffab40", "#ff7220", "#f44336", "#ff1744", "#a5014a"],
    "rainfall": {SELECTED_COUNTRY: "#5a93c7", "Median (All Countries)": "#236494"},
    "sea_surface": ["#5a93c7", "#236494"],
    "crop": ["#3d860b", "#00610e", "#5a93c7", "#236494", "#11487a"],
    "livestock": ["#eae88e", "#a0dd8e"],
    "livestock_rank": ["#eae88e", "#d6e590", "#c0df8c", "#b1df8e", "#a0dd8e"],
    "power": {"Regional Median (Total Generation)": "#FFA500", SELECTED_COUNTRY: "#FFD700"},
    "tourism": ["#007BFF", "#6C757D"],
}


# --------------------------------------------------------------------------
# 1. Data loading & consolidation
# --------------------------------------------------------------------------

def load_datasets() -> dict[str, pd.DataFrame]:
    """Download every raw CSV and return them keyed by short name."""
    return {
        name: pd.read_csv(f"{DATA_BASE_URL}{fname}")
        for name, fname in DATA_FILES.items()
    }


def standardize_columns(datasets: dict[str, pd.DataFrame]) -> list[str]:
    """Rename shared columns, enforce dtypes, and return the master country list.

    Mirrors notebook section "A) Rename Columns and Consolidate Countries".
    """
    all_countries: set[str] = set()

    for df in datasets.values():
        if "TIME_PERIOD" in df.columns:
            df.rename(columns={"TIME_PERIOD": "Year"}, inplace=True)
        if "Pacific Island Countries and territories" in df.columns:
            df.rename(columns={"Pacific Island Countries and territories": "Country"}, inplace=True)

        if "Year" in df.columns:
            df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
        if "Country" in df.columns:
            df["Country"] = df["Country"].astype(str)
            all_countries.update(df["Country"].dropna().unique())

    return sorted(all_countries)


def filter_and_rename(
    df: pd.DataFrame,
    filters: dict[str, str],
    value_col_new: str,
    value_col_old: str = "OBS_VALUE",
) -> pd.DataFrame:
    """Apply column-value filters, rename the observation column, and cast dtypes.

    This is step 1 of the repeated recipe (filter + rename + cast) used at the
    top of nearly every section in the notebook.
    """
    mask = pd.Series(True, index=df.index)
    for col, val in filters.items():
        mask &= df[col] == val
    out = df[mask].copy()

    if value_col_old in out.columns:
        out.rename(columns={value_col_old: value_col_new}, inplace=True)

    if "Year" in out.columns:
        out["Year"] = pd.to_numeric(out["Year"], errors="coerce").astype("Int64")
    if "Country" in out.columns:
        out["Country"] = out["Country"].astype(str)

    return out


# --------------------------------------------------------------------------
# 2. Shared "country vs. regional median" line-chart recipe
#    (covers sections B, D, E, F, J, L)
# --------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    figure: go.Figure
    country_data: pd.DataFrame
    median_by_year: pd.DataFrame
    median_col: str


def trend_description(
    series_df: pd.DataFrame,
    value_col: str,
    unit: str,
    threshold: float,
    num_years: int = NUM_YEARS_FOR_TREND,
    stat: str = "mean",
) -> str:
    """Describe whether a series is trending up, down, or flat.

    Consolidates the half-dozen near-identical `get_*_trend_description`
    helper functions scattered across the notebook (temperature, rainfall,
    sea surface, crop, livestock, tourism all had their own copy).
    """
    agg = (lambda s: s.mean()) if stat == "mean" else (lambda s: s.median())

    if len(series_df) < num_years * 2:
        avg = agg(series_df[value_col])
        return f"an average of {avg:.2f}{unit} throughout the period"

    start_avg = agg(series_df[value_col].head(num_years))
    end_avg = agg(series_df[value_col].tail(num_years))

    if end_avg > start_avg + threshold:
        return f"a significant increasing trend, from {start_avg:.2f}{unit} to {end_avg:.2f}{unit} in recent years"
    if end_avg < start_avg - threshold:
        return f"a significant decreasing trend, from {start_avg:.2f}{unit} to {end_avg:.2f}{unit} in recent years"
    return f"a relatively stable trend, with an average around {start_avg:.2f}{unit}"


def build_comparison_chart(
    df: pd.DataFrame,
    value_col: str,
    country: str,
    unit: str,
    title: str,
    y_axis_title: str,
    colors,
    hover_precision: str = ".2f",
    agg: str = "median",
) -> ComparisonResult:
    """Build the recurring "selected country vs. regional median" line chart.

    Replaces the duplicated logic in sections B (temperature), D (rainfall),
    E (sea surface), F (crop yield), J (livestock), and L (tourism).
    """
    median_col = f"Overall_Median_{value_col}"
    aggfunc = "median" if agg == "median" else "mean"

    median_by_year = (
        df.groupby("Year")[value_col].agg(aggfunc).reset_index().rename(columns={value_col: median_col})
    )

    country_data = df[df["Country"] == country].copy()
    country_data = pd.merge(country_data, median_by_year, on="Year", how="left")

    median_line = median_by_year.copy()
    median_line["Country"] = "Median (All Countries)"
    median_line[value_col] = median_line[median_col]

    plot_data = pd.concat(
        [
            country_data[["Year", "Country", value_col, median_col]],
            median_line[["Year", "Country", value_col, median_col]],
        ],
        ignore_index=True,
    )

    color_kwargs = (
        {"color_discrete_map": colors} if isinstance(colors, dict) else {"color_discrete_sequence": colors}
    )

    fig = px.line(
        plot_data,
        x="Year",
        y=value_col,
        color="Country",
        title=title,
        labels={"Year": "Year", value_col: y_axis_title},
        **color_kwargs,
    )
    fig.update_layout(title_text=title, xaxis_title="Year", yaxis_title=y_axis_title,
                       hovermode="closest", title_x=0.5)

    for trace in fig.data:
        if trace.name == country:
            trace_data = plot_data[plot_data["Country"] == country]
            trace.customdata = np.stack([trace_data[median_col]], axis=-1)
            trace.hovertemplate = (
                "<b>Year</b>: %{x}<br>"
                f"<b>Country</b>: {country}<br>"
                f"<b>{country} {y_axis_title}</b>: %{{y:{hover_precision}}}{unit}<br>"
                f"<b>Overall Median</b>: %{{customdata[0]:{hover_precision}}}{unit}<extra></extra>"
            )
        else:
            trace.hovertemplate = (
                "<b>Year</b>: %{x}<br><b>Country</b>: Median (All Countries)<br>"
                f"<b>Median {y_axis_title}</b>: %{{y:{hover_precision}}}{unit}<extra></extra>"
            )

    return ComparisonResult(figure=fig, country_data=country_data, median_by_year=median_line, median_col=median_col)


def comparison_insight_markdown(
    country: str,
    label: str,
    country_data: pd.DataFrame,
    median_by_year: pd.DataFrame,
    value_col: str,
    median_col: str,
    unit: str,
    threshold: float,
) -> str:
    """Generate the recurring "Dynamic Insight" markdown block.

    Consolidates the templated insight text repeated after every comparison
    chart in the notebook (temperature, rainfall, sea surface, crop yield,
    livestock, tourism).
    """
    country_data = country_data.sort_values("Year")
    median_by_year = median_by_year.sort_values("Year")

    start_year, end_year = country_data["Year"].min(), country_data["Year"].max()
    country_trend = trend_description(country_data, value_col, unit, threshold)
    median_trend = trend_description(median_by_year, value_col, unit, threshold)

    last_val = country_data[value_col].iloc[-1]
    last_median = median_by_year[value_col].iloc[-1]
    if last_val > last_median + threshold:
        comparison = f"{country}'s recent values are notably higher than the regional median. "
    elif last_val < last_median - threshold:
        comparison = f"{country}'s recent values are notably lower than the regional median. "
    else:
        comparison = f"{country}'s recent values closely align with the regional median. "

    max_val, min_val = country_data[value_col].max(), country_data[value_col].min()
    max_year = country_data.loc[country_data[value_col].idxmax(), "Year"]
    min_year = country_data.loc[country_data[value_col].idxmin(), "Year"]

    return f"""
### Dynamic Insight for {country} ({label}):

**Overview ({start_year}-{end_year}):**

Between {start_year} and {end_year}, {country} has experienced {country_trend}. Values ranged from a low
of **{min_val:.2f}{unit}** (around {min_year}) to a high of **{max_val:.2f}{unit}** (around {max_year}).

During the same period, the **regional median** has shown {median_trend}.

**Comparison:**

{comparison}
"""


# --------------------------------------------------------------------------
# 3. Shared "tail risk" recipe (covers sections H, I)
# --------------------------------------------------------------------------

def tail_risk_chart(
    country_data: pd.DataFrame,
    value_col: str,
    country: str,
    unit: str,
    color: str,
    title: str,
) -> tuple[go.Figure, pd.DataFrame, float]:
    """Flag +/-2 standard deviation events and plot them against the raw series.

    Consolidates sections H (temperature tail risk) and I (rainfall tail risk),
    which were otherwise identical apart from the value column and units.
    """
    country_data = country_data.sort_values("Year").dropna(subset=[value_col])
    mean_val = country_data[value_col].mean()
    std_val = country_data[value_col].std()
    threshold = 2 * std_val

    extremes = country_data[
        (country_data[value_col] > threshold) | (country_data[value_col] < -threshold)
    ].copy()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=country_data["Year"], y=country_data[value_col], mode="lines", name=f"{value_col}",
        line=dict(color="lightgrey", width=1),
        hovertemplate=f"<b>Year</b>: %{{x}}<br><b>Anomaly</b>: %{{y:.2f}}{unit}<extra></extra>",
    ))
    if not extremes.empty:
        fig.add_trace(go.Scatter(
            x=extremes["Year"], y=extremes[value_col], mode="markers", name="Extreme Events",
            marker=dict(color=color, size=8, symbol="circle-open", line=dict(width=2)),
            hovertemplate=f"<b>Extreme Year</b>: %{{x}}<br><b>Extreme Anomaly</b>: %{{y:.2f}}{unit}<extra></extra>",
        ))
    fig.add_hline(y=threshold, line_dash="dot", line_color=color,
                  annotation_text=f"Upper Threshold (+{threshold:.2f}{unit})", annotation_position="top right")
    fig.add_hline(y=-threshold, line_dash="dot", line_color=color,
                  annotation_text=f"Lower Threshold (-{threshold:.2f}{unit})", annotation_position="bottom right")
    fig.update_layout(title=title, xaxis_title="Year", yaxis_title=f"Anomaly ({unit})",
                       hovermode="x unified", title_x=0.5)

    return fig, extremes, threshold


def tail_risk_insight_markdown(
    country: str, label: str, country_data: pd.DataFrame, value_col: str,
    extremes: pd.DataFrame, threshold: float, unit: str,
) -> str:
    start_year, end_year = country_data["Year"].min(), country_data["Year"].max()
    highest = country_data[value_col].max()
    highest_year = country_data.loc[country_data[value_col].idxmax(), "Year"]
    lowest = country_data[value_col].min()
    lowest_year = country_data.loc[country_data[value_col].idxmin(), "Year"]

    return f"""
### Dynamic Insight for {country} (Historical Tail-Risk Analysis - {label}):

**Overview ({start_year}-{end_year}):**

Extreme events are defined as anomalies exceeding **{threshold:.2f}{unit}** above or below average
(two standard deviations from the historical mean).

**Key Observations:**

* **Number of Extreme Events:** {len(extremes)}
* **Highest Anomaly:** {highest:.2f}{unit} in {highest_year}
* **Lowest Anomaly:** {lowest:.2f}{unit} in {lowest_year}
"""


# --------------------------------------------------------------------------
# 4. Shared heatmap & top/bottom bar-chart recipes
#    (covers sections F-heatmap, F-ranking, J-heatmap, J-ranking, K-heatmap)
# --------------------------------------------------------------------------

def build_product_heatmap(
    df: pd.DataFrame, product_col: str, value_col: str, colorscale, title: str, unit: str,
    aggfunc: str = "median",
) -> tuple[go.Figure, pd.DataFrame]:
    """Pivot product x year and render as a heatmap.

    Consolidates the crop-yield heatmap (F), livestock heatmap (J), and power
    generation source heatmap (K), which shared an identical pivot/plot shape.
    """
    pivot = (
        df.groupby([product_col, "Year"])[value_col].agg(aggfunc).reset_index()
        .pivot_table(index=product_col, columns="Year", values=value_col, aggfunc=aggfunc)
        .sort_index(axis=0)
    )
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index, colorscale=colorscale,
        colorbar_title=f"{value_col} ({unit})",
        hovertemplate=f"<b>%{{y}}</b><br><b>Year</b>: %{{x}}<br><b>Value</b>: %{{z:.2f}} {unit}<extra></extra>",
    ))
    fig.update_layout(
        title_text=title, xaxis_title="Year", yaxis_title=product_col, title_x=0.5,
        height=max(400, pivot.shape[0] * 25 + 200),
    )
    return fig, pivot


def build_top_bottom_bars(
    df: pd.DataFrame, group_col: str, value_col: str, unit: str, country: str,
    label: str, colors: list[str], n: int = 10,
) -> tuple[go.Figure, go.Figure, pd.DataFrame, pd.DataFrame]:
    """Build matching top-N / bottom-N horizontal bar charts.

    Consolidates the ranked-products bar charts in sections F (crop yield)
    and J (livestock yield).
    """
    agg = df.groupby(group_col)[value_col].median().reset_index()
    top = agg.sort_values(value_col, ascending=False).head(n)
    bottom = agg.sort_values(value_col, ascending=True).head(n)

    def _bar(data, colorscale, order, title):
        fig = px.bar(
            data, x=value_col, y=group_col, orientation="h", title=title,
            labels={value_col: f"Median {label} ({unit})", group_col: group_col},
            color=value_col, color_continuous_scale=colorscale, text_auto=".2f",
        )
        fig.update_layout(yaxis={"categoryorder": order}, title_x=0.5, coloraxis_showscale=False)
        return fig

    fig_top = _bar(top, colors, "total ascending", f"Top {n} {label} by Median Yield in {country} ({unit})")
    fig_bottom = _bar(bottom, colors[::-1], "total descending", f"Bottom {n} {label} by Median Yield in {country} ({unit})")
    return fig_top, fig_bottom, top, bottom


# --------------------------------------------------------------------------
# 5. Section functions (the notebook's A-L headings)
# --------------------------------------------------------------------------

def section_temperature(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """B) + C) Mean Surface Temperature Anomalies."""
    df = filter_and_rename(
        datasets["mean_surface_temp_anomalies"],
        {"UNIT_MEASURE": "CELSIUS", "CLIMATE_CHANGE_INDICATORS": "ST_ANOM"},
        "Temperature_Anomaly",
    )
    result = build_comparison_chart(
        df, "Temperature_Anomaly", country, "°C",
        f"Mean Surface Temperature Anomalies for {country} vs. Overall Median (Celsius)",
        "Temperature Anomaly (°C)", COLORS["temperature"],
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, "Mean Surface Temperature Anomalies", result.country_data, result.median_by_year,
        "Temperature_Anomaly", result.median_col, "°C", threshold=0.1,
    )))
    return df  # returned for reuse by the tail-risk section


def section_rainfall(datasets: dict[str, pd.DataFrame], country: str) -> pd.DataFrame:
    """D) Rainfall Anomaly Visualization and Dynamic Insight."""
    df = filter_and_rename(
        datasets["rainfall_anomalies"],
        {"CLIMATE_CHANGE_INDICATORS": "RAIN_ANOM", "UNIT_MEASURE": "MM"},
        "Rainfall_Anomaly",
    )
    result = build_comparison_chart(
        df, "Rainfall_Anomaly", country, "mm",
        f"Mean Surface Rainfall Anomalies for {country} vs. Overall Median (mm)",
        "Rainfall Anomaly (mm)", COLORS["rainfall"],
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, "Rainfall Anomalies", result.country_data, result.median_by_year,
        "Rainfall_Anomaly", result.median_col, "mm", threshold=5.0,
    )))
    return df


def section_sea_surface(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """E) Sea Surface Temperature Anomaly Visualization and Dynamic Insight."""
    df = filter_and_rename(
        datasets["mean_sea_surface_temp_anomalies"],
        {"CLIMATE_CHANGE_INDICATORS": "SST_ANOM", "UNIT_MEASURE": "CELSIUS"},
        "Sea_Surface_Temperature_Anomaly",
    )
    result = build_comparison_chart(
        df, "Sea_Surface_Temperature_Anomaly", country, "°C",
        f"Sea Surface Temperature Anomalies for {country} vs. Overall Median (°C)",
        "Sea Surface Temperature Anomaly (°C)", COLORS["sea_surface"],
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, "Sea Surface Temperature Anomalies", result.country_data, result.median_by_year,
        "Sea_Surface_Temperature_Anomaly", result.median_col, "°C", threshold=0.1,
    )))


def section_crop_yield(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """F) Crop Yield Visualization, Ranking, and Heatmap."""
    base = filter_and_rename(
        datasets["crop_yield"], {"AGRICULTURE_PRODUCTION_TYPE": "CROP_YIELD", "UNIT_MEASURE": "KGHA"},
        "Crop_Yield",
    )
    annual = base.groupby(["Country", "Year"])["Crop_Yield"].median().reset_index()

    result = build_comparison_chart(
        annual, "Crop_Yield", country, " KG/HA",
        f"Crop Yield: {country} vs. Global Median (KG/HA)", "Crop Yield (KG/HA)", COLORS["crop"][:2],
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, "Crop Yield", result.country_data, result.median_by_year,
        "Crop_Yield", result.median_col, " KG/HA", threshold=500.0,
    )))

    country_products = base[base["Country"] == country].dropna(subset=["Crop_Yield"])
    fig_top, fig_bottom, top, bottom = build_top_bottom_bars(
        country_products, "Agricultural product", "Crop_Yield", "KG/HA", country, "Agricultural Products",
        COLORS["crop"],
    )
    fig_top.show()
    fig_bottom.show()

    crop_heatmap_scale = [
        [0, "#edf8e9"], [0.2, "#bae4b3"], [0.4, "#74c476"], [0.6, "#31a354"], [0.8, "#006d2c"], [1, "#00441b"],
    ]
    fig_heatmap, pivot = build_product_heatmap(
        country_products, "Agricultural product", "Crop_Yield", crop_heatmap_scale,
        f"Median Crop Yield by Agricultural Product and Year in {country} (KG/HA)", "KG/HA",
    )
    fig_heatmap.show()


def section_tail_risk(country_data: pd.DataFrame, value_col: str, country: str, unit: str, color: str, label: str) -> None:
    """H) / I) Historical Tail-Risk Analysis (temperature and rainfall)."""
    country_series = country_data[country_data["Country"] == country]
    fig, extremes, threshold = tail_risk_chart(
        country_series, value_col, country, unit, color,
        f"Historical Tail-Risk Analysis: {label} for {country}",
    )
    fig.show()
    ipd.display(ipd.Markdown(tail_risk_insight_markdown(
        country, label, country_series.sort_values("Year").dropna(subset=[value_col]),
        value_col, extremes, threshold, unit,
    )))


def section_livestock(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """J) Livestock Yield Visualization, Ranking, and Heatmap."""
    base = filter_and_rename(
        datasets["livestock_yield"], {"AGRICULTURE_PRODUCTION_TYPE": "LVST_YIELD", "UNIT_MEASURE": "KG_AN"},
        "Livestock_Yield",
    )
    annual = base.groupby(["Country", "Year"])["Livestock_Yield"].median().reset_index()

    result = build_comparison_chart(
        annual, "Livestock_Yield", country, " KG/AN",
        f"Livestock Yield for {country} vs. Overall Median (KG/AN)", "Livestock Yield (KG/AN)",
        COLORS["livestock"],
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, "Livestock Yield", result.country_data, result.median_by_year,
        "Livestock_Yield", result.median_col, " KG/AN", threshold=5.0,
    )))

    country_products = base[base["Country"] == country].dropna(subset=["Livestock_Yield"])
    fig_top, fig_bottom, top, bottom = build_top_bottom_bars(
        country_products, "Agricultural product", "Livestock_Yield", "KG/AN", country, "Livestock Products",
        COLORS["livestock_rank"],
    )
    fig_top.show()
    fig_bottom.show()

    lvst_heatmap_scale = [[0.0, "#eae88e"], [0.25, "#d6e590"], [0.5, "#c0df8c"], [0.75, "#b1df8e"], [1.0, "#a0dd8e"]]
    fig_heatmap, pivot = build_product_heatmap(
        country_products, "Agricultural product", "Livestock_Yield", lvst_heatmap_scale,
        f"Median Livestock Yield by Product and Year in {country} (KG/AN)", "KG/AN",
    )
    fig_heatmap.show()


def section_power_generation(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """K) Power Generation: totals line chart, source heatmap, and Sankey flow."""
    raw = datasets["power_generation"]

    # Totals: country vs. regional median, summed across non-"Total" sources
    base = raw[(raw["UNIT_MEASURE"] == "GWH") & (~raw["Energy source"].str.contains("Total", case=False, na=False))].copy()
    base["Year"] = pd.to_numeric(base["Year"], errors="coerce")
    base["OBS_VALUE"] = pd.to_numeric(base["OBS_VALUE"], errors="coerce")
    base = base.dropna(subset=["Year", "OBS_VALUE"])

    annual_totals = base.groupby(["Country", "Year"])["OBS_VALUE"].sum().reset_index().rename(columns={"OBS_VALUE": "Total_GWH"})
    regional_median = annual_totals.groupby("Year")["Total_GWH"].median().reset_index().rename(columns={"Total_GWH": "Regional_Median_GWH"})

    country_line = annual_totals[annual_totals["Country"] == country].copy()
    benchmark_line = regional_median.copy()
    benchmark_line["Country"] = "Regional Median (Total Generation)"
    benchmark_line.rename(columns={"Regional_Median_GWH": "Total_GWH"}, inplace=True)
    plot_data = pd.concat([country_line, benchmark_line], ignore_index=True)

    fig_power = px.line(
        plot_data, x="Year", y="Total_GWH", color="Country",
        title=f"Corrected Power Generation: {country} vs. Regional Median (GWH)",
        labels={"Total_GWH": "Total Generation (GWH)", "Year": "Year"},
        color_discrete_map=COLORS["power"],
    )
    fig_power.update_layout(title_x=0.5, template="plotly_white", hovermode="x unified")
    fig_power.show()

    # Source-by-year heatmap for the selected country only
    heatmap_mask = (
        (raw["Country"] == country) & (raw["Grid connection status"] == "Total") &
        (raw["UNIT_MEASURE"] == "GWH") & (~raw["Energy source"].str.contains("Total", case=False, na=False))
    )
    heatmap_base = raw[heatmap_mask].copy()
    heatmap_base["Year"] = pd.to_numeric(heatmap_base["Year"], errors="coerce")
    heatmap_base["OBS_VALUE"] = pd.to_numeric(heatmap_base["OBS_VALUE"], errors="coerce")
    heatmap_base = heatmap_base.dropna(subset=["Year", "OBS_VALUE", "Energy source"])

    fig_heatmap, power_pivot = build_product_heatmap(
        heatmap_base.rename(columns={"OBS_VALUE": "Generation"}), "Energy source", "Generation",
        "YlOrRd", f"Power Generation by Energy Source: {country} (GWH)", "GWH", aggfunc="sum",
    )
    fig_heatmap.show()

    if not power_pivot.empty:
        latest_year, start_year = power_pivot.columns.max(), power_pivot.columns.min()
        latest_mix = power_pivot[latest_year].sort_values(ascending=False)
        primary_source, primary_val, total_gen = latest_mix.index[0], latest_mix.iloc[0], latest_mix.sum()
        trend_status = "growth" if total_gen > power_pivot[start_year].sum() else "contraction"
        ipd.display(ipd.Markdown(f"""
### Dynamic Insight for {country} (Power Generation Mix):

Between {start_year} and {latest_year}, {country}'s power generation has shown a general {trend_status}.
As of {latest_year}, total generation reached **{total_gen:.1f} GWH**, led by **{primary_source}**
({primary_val:.1f} GWH).
"""))

    # Sankey: energy source -> grid connection status
    sankey_df = raw[
        (raw["Country"] == country) & (raw["UNIT_MEASURE"] == "GWH") &
        (raw["Grid connection status"].isin(["Off-grid", "On-grid"]))
    ].copy().rename(columns={"OBS_VALUE": "Generation_GWH"})
    sankey_df["Generation_GWH"] = pd.to_numeric(sankey_df["Generation_GWH"], errors="coerce")
    sankey_df.dropna(subset=["Generation_GWH", "Energy source", "Grid connection status"], inplace=True)

    agg_sankey = sankey_df.groupby(["Energy source", "Grid connection status"])["Generation_GWH"].sum().reset_index()
    all_nodes = pd.concat([agg_sankey["Energy source"], agg_sankey["Grid connection status"]]).unique()
    node_idx = {node: i for i, node in enumerate(all_nodes)}

    fig_sankey = go.Figure(data=[go.Sankey(
        node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=all_nodes, color="blue"),
        link=dict(
            source=agg_sankey["Energy source"].map(node_idx),
            target=agg_sankey["Grid connection status"].map(node_idx),
            value=agg_sankey["Generation_GWH"],
            hovertemplate="<b>Source</b>: %{source.label}<br><b>Target</b>: %{target.label}<br><b>Generation</b>: %{value:.1f} GWH<extra></extra>",
        ),
    )])
    min_year, max_year = sankey_df["Year"].min(), sankey_df["Year"].max()
    fig_sankey.update_layout(
        title_text=f"Power Generation Flow for {country} ({min_year}-{max_year})<br>Energy Source to Grid Connection Status (GWH)",
        font_size=10, title_x=0.5, height=600,
    )
    fig_sankey.show()

    if not agg_sankey.empty:
        on_grid = agg_sankey[agg_sankey["Grid connection status"] == "On-grid"]
        off_grid = agg_sankey[agg_sankey["Grid connection status"] == "Off-grid"]
        on_note = (f"**{on_grid.loc[on_grid['Generation_GWH'].idxmax(), 'Energy source']}** leads On-grid supply."
                   if not on_grid.empty else "No significant On-grid generation.")
        off_note = (f"**{off_grid.loc[off_grid['Generation_GWH'].idxmax(), 'Energy source']}** leads Off-grid supply."
                    if not off_grid.empty else "No significant Off-grid generation.")
        ipd.display(ipd.Markdown(f"""
### Dynamic Insight for {country}'s Power Generation Flow ({min_year}-{max_year}):

Total power generation across On-grid and Off-grid was **{agg_sankey['Generation_GWH'].sum():.1f} GWH**.
{on_note} {off_note}
"""))


def section_tourism(datasets: dict[str, pd.DataFrame], country: str) -> None:
    """L) Tourism Arrivals Visualization and Dynamic Insight."""
    # Note: the source notebook filters on "Overnight tourists" here but labels
    # the insight text "Overnight visitor" (cells 64 vs. 66 disagreed). We keep
    # the filter that actually matches the data.
    visitor_category = "Overnight tourists"
    df = filter_and_rename(
        datasets["tourist_arrivals"],
        {"Visitor duration category": visitor_category, "UNIT_MEASURE": "N"},
        "Tourism_Arrivals",
    )
    df.dropna(subset=["Tourism_Arrivals", "Year", "Country"], inplace=True)
    annual = df.groupby(["Country", "Year"])["Tourism_Arrivals"].sum().reset_index()

    result = build_comparison_chart(
        annual, "Tourism_Arrivals", country, "",
        f"Tourism Arrivals: {country} vs. Regional Median (Overnight Tourists)",
        "Number of Tourism Arrivals", COLORS["tourism"], hover_precision=",.0f",
    )
    result.figure.show()
    ipd.display(ipd.Markdown(comparison_insight_markdown(
        country, f"Tourism Arrivals ({visitor_category})", result.country_data, result.median_by_year,
        "Tourism_Arrivals", result.median_col, "", threshold=1000,
    )))


# --------------------------------------------------------------------------
# 6. Orchestration
# --------------------------------------------------------------------------

def main(country: str = SELECTED_COUNTRY) -> None:
    datasets = load_datasets()
    standardize_columns(datasets)

    temp_df = section_temperature(datasets, country)
    rainfall_df = section_rainfall(datasets, country)
    section_sea_surface(datasets, country)
    section_crop_yield(datasets, country)

    section_tail_risk(temp_df, "Temperature_Anomaly", country, "°C", "red", "Mean Surface Temperature Anomalies")
    section_tail_risk(rainfall_df, "Rainfall_Anomaly", country, "mm", "blue", "Rainfall Anomalies")

    section_livestock(datasets, country)
    section_power_generation(datasets, country)
    section_tourism(datasets, country)


if __name__ == "__main__":
    main()
