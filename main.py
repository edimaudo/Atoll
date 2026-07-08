from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
import data
import plotly.express as px

app = FastAPI(title="Pacific Island & Territories Climate Change")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the landing page."""
    return templates.TemplateResponse("index.html", {"request": request})

# @app.get("/app", response_class=HTMLResponse)
# async def app_page(request: Request):
#     """Main app page"""
#     return templates.TemplateResponse("app.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """Talks about the challenge and data."""
    return templates.TemplateResponse("about.html", {"request": request})

@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return HTMLResponse(str(exc.detail), status_code=exc.status_code)

@app.get("/app", response_class=HTMLResponse)
async def insights(request: Request, country: str = "New Zealand"):
    # In FastAPI, query parameters are defined as function arguments.
    # The default is strictly set to "New Zealand".
    
    plots = {}

    try:
        # 1. Sea Surface Temp Anomaly (Line Chart)
        df1 = data.mean_sea_surface_temp_anomaly[data.mean_sea_surface_temp_anomaly['country'] == country]
        fig1 = px.line(df1, x='year', y='value', title="Mean Sea Surface Temperature Anomaly")
        # include_plotlyjs='cdn' is used ONLY on the first chart so the library loads once
        plots['sea_temp'] = fig1.to_html(full_html=False, include_plotlyjs='cdn')

        # 2. Crop Yield (Bar Chart)
        df2 = data.crop_yield[data.crop_yield['country'] == country]
        fig2 = px.bar(df2, x='year', y='value', title="Crop Yield (Disaggregated)")
        # All subsequent charts set include_plotlyjs=False to prevent loading the 3MB library 11 times
        plots['crop'] = fig2.to_html(full_html=False, include_plotlyjs=False)

        # 3. Environmental Tax (Area Chart)
        df3 = data.environmental_tax[data.environmental_tax['country'] == country]
        fig3 = px.area(df3, x='year', y='value', title="Environmental Taxes")
        plots['tax'] = fig3.to_html(full_html=False, include_plotlyjs=False)

        # 4. Greenhouse Gas Emissions (Scatter Plot)
        df4 = data.greenhouse_gas_emissions[data.greenhouse_gas_emissions['country'] == country]
        fig4 = px.scatter(df4, x='year', y='value', title="Greenhouse Gas Emissions per Capita")
        plots['ghg'] = fig4.to_html(full_html=False, include_plotlyjs=False)

        # 5. Livestock Yield (Bar Chart)
        df5 = data.livestock_yield[data.livestock_yield['country'] == country]
        fig5 = px.bar(df5, x='year', y='value', title="Livestock Yield")
        plots['livestock'] = fig5.to_html(full_html=False, include_plotlyjs=False)

        # 6. Mean Surface Temp Anomaly (Line Chart)
        df6 = data.mean_surface_temp_anomaly[data.mean_surface_temp_anomaly['country'] == country]
        fig6 = px.line(df6, x='year', y='value', title="Mean Surface Temperature Anomaly")
        plots['surface_temp'] = fig6.to_html(full_html=False, include_plotlyjs=False)

        # 7. Meteorological Monitoring (Bar Chart)
        df7 = data.meterological_monitor[data.meterological_monitor['country'] == country]
        fig7 = px.bar(df7, x='year', y='value', title="Meteorological Monitoring Network")
        plots['meteo'] = fig7.to_html(full_html=False, include_plotlyjs=False)

        # 8. Power Generation (Bar Chart with color source)
        df8 = data.power_generation[data.power_generation['country'] == country]
        fig8 = px.bar(df8, x='year', y='value', color='source', title="Power Generation by Source") 
        plots['power'] = fig8.to_html(full_html=False, include_plotlyjs=False)

        # 9. Rainfall Anomaly (Line Chart)
        df9 = data.rainfall_anomaly[data.rainfall_anomaly['country'] == country]
        fig9 = px.line(df9, x='year', y='value', title="Rainfall Anomalies")
        plots['rainfall'] = fig9.to_html(full_html=False, include_plotlyjs=False)

        # 10. Sea Level Anomaly (Line Chart)
        df10 = data.sea_level_anomaly[data.sea_level_anomaly['country'] == country]
        fig10 = px.line(df10, x='year', y='value', title="Sea Level Anomalies")
        plots['sea_level'] = fig10.to_html(full_html=False, include_plotlyjs=False)

        # 11. Tourist Arrivals (Bar Chart)
        df11 = data.tourism_arrival[data.tourism_arrival['country'] == country]
        fig11 = px.bar(df11, x='year', y='value', title="Tourist Arrivals")
        plots['tourism'] = fig11.to_html(full_html=False, include_plotlyjs=False)

    except Exception as e:
        print(f"Visualization Error: {e}")

    # FastAPI TemplateResponse REQUIRES the 'request' object to be passed in the context
    return templates.TemplateResponse(
        "app.html", 
        {
            "request": request, 
            "selected_country": country, 
            "plots": plots
        }
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
