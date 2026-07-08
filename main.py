from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
# from data import *


app = FastAPI(title="Pacific Island & Territories Climate Change")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the landing page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """Talks about the challenge and data."""
    return templates.TemplateResponse("about.html", {"request": request})

@app.exception_handler(404)
async def custom_404_handler(request: Request, _exc):
    return templates.TemplateResponse(request, "404.html", status_code=404)

# @app.get("/app", response_class=HTMLResponse)
# async def insights(request: Request, country: str = "New Zealand"):
#     # async def app_page(request: Request):

#     return templates.TemplateResponse("app.html", {"request": request})
    # plots = {}
    # insights_text = {}

    # try:
    #     # ==========================================
    #     # CATEGORY 1: AGRO-ECOSYSTEMS & FOOD SECURITY
    #     # ==========================================
        
    #     # 1. Crop Yield
    #     df_crop = data.crop_yield[data.crop_yield['country'] == country]
    #     fig_crop = px.bar(df_crop, x='year', y='value', title="Crop Yield Trends (Disaggregated)")
    #     # Include Plotly JS CDN once on the very first chart loaded
    #     plots['crop'] = fig_crop.to_html(full_html=False, include_plotlyjs='cdn')

        # # 2. Livestock Yield
        # df_live = data.livestock_yield[data.livestock_yield['country'] == country]
        # fig_live = px.bar(df_live, x='year', y='value', title="Livestock Productive Yield")
        # plots['livestock'] = fig_live.to_html(full_html=False, include_plotlyjs=False)

        # # 3. Meteorological Monitoring Network
        # df_met = data.meterological_monitor[data.meterological_monitor['country'] == country]
        # fig_met = px.line(df_met, x='year', y='value', title="Meteorological Station Monitoring Infrastructure")
        # plots['meteo'] = fig_met.to_html(full_html=False, include_plotlyjs=False)

        # # Dynamic placeholder text for Agro-Ecosystems
        # insights_text['agro'] = (
        #     f"Aggregated agricultural observations for {country} demonstrate how local production capacity "
        #     f"correlates with regional monitoring networks. Shifts in crop indices and livestock yield values "
        #     f"reflect immediate baseline interactions with shifting environmental variables."
        # )

        # # ==========================================
        # # CATEGORY 2: OCEAN HEALTH & CLIMATE ANOMALIES
        # # ==========================================
        
        # # 4. Mean Sea Surface Temperature Anomaly
        # df_sst = data.mean_sea_surface_temp_anomaly[data.mean_sea_surface_temp_anomaly['country'] == country]
        # fig_sst = px.line(df_sst, x='year', y='value', title="Mean Sea Surface Temperature Anomaly")
        # plots['sea_temp'] = fig_sst.to_html(full_html=False, include_plotlyjs=False)

        # # 5. Mean Surface Temperature Anomaly
        # df_surf = data.mean_surface_temp_anomaly[data.mean_surface_temp_anomaly['country'] == country]
        # fig_surf = px.line(df_surf, x='year', y='value', title="Mean Land Surface Temperature Anomaly")
        # plots['surface_temp'] = fig_surf.to_html(full_html=False, include_plotlyjs=False)

        # # 6. Rainfall Anomaly
        # df_rain = data.rainfall_anomaly[data.rainfall_anomaly['country'] == country]
        # fig_rain = px.bar(df_rain, x='year', y='value', title="Precipitation & Rainfall Anomalies")
        # plots['rainfall'] = fig_rain.to_html(full_html=False, include_plotlyjs=False)

        # # 7. Sea Level Anomaly
        # df_sea = data.sea_level_anomaly[data.sea_level_anomaly['country'] == country]
        # fig_sea = px.line(df_sea, x='year', y='value', title="Sea Level Absolute Anomalies")
        # plots['sea_level'] = fig_sea.to_html(full_html=False, include_plotlyjs=False)

        # # Dynamic placeholder text for Ocean Health
        # insights_text['ocean'] = (
        #     f"Oceanic indicators for {country} provide an assessment of marine variance. "
        #     f"Sea surface deviations alongside localized sea level trends show the direct exposure "
        #     f"this territory faces from macroclimate fluctuations."
        # )

        # # ==========================================
        # # CATEGORY 3: SOCIO-ECONOMICS & EMISSIONS
        # # ==========================================
        
        # # 8. Environmental Taxes
        # df_tax = data.environmental_tax[data.environmental_tax['country'] == country]
        # fig_tax = px.area(df_tax, x='year', y='value', title="Environmental Taxes & Revenue Structures")
        # plots['tax'] = fig_tax.to_html(full_html=False, include_plotlyjs=False)

        # # 9. Greenhouse Gas Emissions
        # # Treating greenhouse gas emissions per capita as a vital socio-economic development byproduct
        # df_ghg = data.greenhouse_gas_emissions[data.greenhouse_gas_emissions['country'] == country]
        # fig_ghg = px.scatter(df_ghg, x='year', y='value', title="Greenhouse Gas Emissions per Capita")
        # plots['ghg'] = fig_ghg.to_html(full_html=False, include_plotlyjs=False)

        # # 10. Power Generation
        # df_pow = data.power_generation[data.power_generation['country'] == country]
        # fig_pow = px.bar(df_pow, x='year', y='value', color='source' if 'source' in df_pow.columns else None, title="Power Generation Matrix Profile")
        # plots['power'] = fig_pow.to_html(full_html=False, include_plotlyjs=False)

        # # 11. Tourist Arrivals
        # df_tour = data.tourism_arrival[data.tourism_arrival['country'] == country]
        # fig_tour = px.bar(df_tour, x='year', y='value', title="International Tourist Arrival Volume")
        # plots['tourism'] = fig_tour.to_html(full_html=False, include_plotlyjs=False)

        # Dynamic placeholder text for Socio-Economics
    #     insights_text['socio'] = (
    #         f"Socio-economic dimensions for {country} detail the intersection of market drivers and fiscal "
    #         f"safeguards. Resource inputs via power grids and tourism streams align against regulatory frameworks "
    #         f"like national environmental tax collections."
    #     )

    # except Exception as e:
    #     print(f"Error processing visual modules: {str(e)}")

    # return templates.TemplateResponse(
    #     "app.html", 
    #     {
    #         "request": request, 
    #         "selected_country": country, 
    #         "plots": plots,
    #         "insights_text": insights_text
    #     }
    # )


