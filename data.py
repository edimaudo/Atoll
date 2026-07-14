import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import ruptures as rpt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import grangercausalitytests
import xgboost as xgb
import json



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


COUNTRY_LIST = [
    'American Samoa', 'Cook Islands', 'Fiji', 'French Polynesia', 'Guam',
    'Kiribati', 'Marshall Islands', 'Micronesia, Federated State of', 'Nauru',
    'New Caledonia', 'Niue', 'Northern Mariana Islands', 'Palau', 'Papua New Guinea',
    'Pitcairn', 'Samoa', 'Solomon Islands', 'Tokelau', 'Tonga', 'Tuvalu',
    'Vanuatu', 'Wallis and Futuna'
]

PACIFIC_COORDS = {
    'American Samoa': {'code': 'AS', 'lat': -14.2710, 'lon': -170.1320},
    'Cook Islands': {'code': 'CK', 'lat': -21.2360, 'lon': -159.7770},
    'Fiji': {'code': 'FJ', 'lat': -17.7134, 'lon': 178.0650},
    'French Polynesia': {'code': 'PF', 'lat': -17.6797, 'lon': -149.4068},
    'Guam': {'code': 'GU', 'lat': 13.4443, 'lon': 144.7937},
    'Kiribati': {'code': 'KI', 'lat': 1.8360, 'lon': -157.3660},
    'Marshall Islands': {'code': 'MH', 'lat': 7.1315, 'lon': 171.1845},
    'Micronesia, Federated State of': {'code': 'FM', 'lat': 7.4250, 'lon': 150.5500},
    'Nauru': {'code': 'NR', 'lat': -0.5228, 'lon': 166.9315},
    'New Caledonia': {'code': 'NC', 'lat': -20.9043, 'lon': 165.6180},
    'Niue': {'code': 'NU', 'lat': -19.0544, 'lon': -169.8672},
    'Northern Mariana Islands': {'code': 'MP', 'lat': 15.0979, 'lon': 145.6739},
    'Palau': {'code': 'PW', 'lat': 7.5149, 'lon': 134.5825},
    'Papua New Guinea': {'code': 'PG', 'lat': -6.3149, 'lon': 143.9555},
    'Pitcairn': {'code': 'PN', 'lat': -25.0667, 'lon': -130.1000},
    'Samoa': {'code': 'WS', 'lat': -13.7590, 'lon': -172.1046},
    'Solomon Islands': {'code': 'SB', 'lat': -9.6457, 'lon': 160.1562},
    'Tokelau': {'code': 'TK', 'lat': -9.2000, 'lon': -171.8480},
    'Tonga': {'code': 'TO', 'lat': -21.1789, 'lon': -175.1982},
    'Tuvalu': {'code': 'TV', 'lat': -8.5146, 'lon': 179.1940},
    'Vanuatu': {'code': 'VU', 'lat': -15.3767, 'lon': 166.9592},
    'Wallis and Futuna': {'code': 'WF', 'lat': -13.7687, 'lon': -177.1560}
}


# Data clean up

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
