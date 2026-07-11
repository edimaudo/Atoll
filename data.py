import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# Load Datasets
path = "/data/"
mean_sea_surface_temp_anomaly = pd.read_csv(path + "Mean sea surface temperature anomalies.csv")
crop_yield = pd.read_csv(path + "Crop yield (disaggregated).csv")
environmental_tax = pd.read_csv(path + "Environmental taxes (disaggregated).csv")
greenhouse_gas_emissions = pd.read_csv(path + "Greenhouse gas emissions per capita.csv")
livestock_yield = pd.read_csv(path + "Livestock yield (disaggregated).csv")
mean_surface_temp_anomaly = pd.read_csv(path + "Mean surface temperature anomalies.csv")
meterological_monitoring = pd.read_csv(path + "Meteorological monitoring network (disaggregated).csv")
power_generation = pd.read_csv(path + "Power generation (disaggregated).csv")
rainfall_anomaly = pd.read_csv(path + "Rainfall anomalies.csv")
sea_level_anomaly = pd.read_csv(path + "Sea level anomalies.csv")
tourism_arrival = pd.read_csv(path + "Tourist arrivals (disaggregated).csv")

datasets = [
    mean_surface_temp_anomaly,
    mean_sea_surface_temp_anomaly,
    crop_yield,
    environmental_tax,
    greenhouse_gas_emissions,
    livestock_yield,
    meteorological_monitoring,
    power_generation,
    rainfall_anomaly,
    sea_level_anomaly,
    tourist_arrivals
]

# Data clean up
all_countries = set()

for i, df in enumerate(datasets):
    # Rename columns for all datasets
    if 'TIME_PERIOD' in df.columns:
        df.rename(columns={'TIME_PERIOD': 'Year'}, inplace=True)
    if 'Pacific Island Countries and territories' in df.columns:
        df.rename(columns={'Pacific Island Countries and territories': 'Country'}, inplace=True)

    # Ensure Year is an integer and Country is a string for all datasets
    if 'Year' in df.columns:
        df['Year'] = pd.to_numeric(df['Year'], errors='coerce').astype('Int64') # Using Int64 for nullable integer
    if 'Country' in df.columns:
        df['Country'] = df['Country'].astype(str)

# Mean surface temperature anomaly update
# 1) Change 'OBS_VALUE' to 'Temperature_Anomaly'
if 'OBS_VALUE' in mean_surface_temp_anomaly.columns:
    mean_surface_temp_anomalies_df.rename(columns={'OBS_VALUE': 'Temperature_Anomaly'}, inplace=True)

# 2) Use filters: 'UNIT_MEASURE' == 'CELSIUS' and 'CLIMATE_CHANGE_INDICATORS' == 'ST_ANOM'
mean_surface_temp_anomaly = mean_surface_temp_anomaly[
    (mean_surface_temp_anomalies_df['UNIT_MEASURE'] == 'CELSIUS') &
    (mean_surface_temp_anomalies_df['CLIMATE_CHANGE_INDICATORS'] == 'ST_ANOM')
].copy() # .copy() to avoid SettingWithCopyWarning

# Rainfall anomaly
# 1) Filter rainfall_anomalies_df
rainfall_anomaly = rainfall_anomaly[
    (rainfall_anomalies_df['CLIMATE_CHANGE_INDICATORS'] == 'RAIN_ANOM') &
    (rainfall_anomalies_df['UNIT_MEASURE'] == 'MM')
].copy()

# 2) Rename 'OBS_VALUE' to 'Rainfall_Anomaly'
if 'OBS_VALUE' in rainfall_anomaly.columns:
    filtered_rainfall_df.rename(columns={'OBS_VALUE': 'Rainfall_Anomaly'}, inplace=True)

# Setup Visualization
