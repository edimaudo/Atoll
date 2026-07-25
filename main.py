import os
from pathlib import Path
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import store
import store_v2
import requests
import json
from fastapi.middleware.gzip import GZipMiddleware

BASE_DIR = Path(__file__).parent

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if path.startswith("vendor/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

app = FastAPI(title="Atoll — Pacific Climate Change")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", CachedStaticFiles(directory=str(BASE_DIR / "static")), name="static") # app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "headline_stat": store.CLIMATE_DATA["headline_stat"],
            "territory_count": len(store.COUNTRY_NAMES),
        },
    )


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request, country: str = store.DEFAULT_COUNTRY, compare: str = ""):
    """v1: line charts for all 7 datasets, compare-aware, one dynamic
    insight per chart, plus the Action Steps dynamic summary + LLM button.
    """
    country, country_data = store.get_country(country)
    compare = store.resolve_compare(country, compare)
    compare_data = store.CLIMATE_DATA["countries"][compare] if compare else None

    insights = {
        key: store_v2.build_indicator_insight_v2(
            country, ind, compare,
            compare_data["indicators"].get(key) if compare_data else None,
        )
        for key, ind in country_data["indicators"].items()
    }

    action_summary = store_v2.build_action_summary_v2(country, country_data, compare, compare_data)

    return templates.TemplateResponse(
        request,
        "app.html",
        {
            "country_names": store.COUNTRY_NAMES,
            "selected_country": country,
            "compare_country": compare,
            "country_data": country_data,
            "chapters": store.CLIMATE_DATA["chapters"],
            "insights": insights,
            "action_summary": action_summary,
            "chart_payload": store.build_chart_payload(country, country_data, compare),
            "all_country_positions": store.CLIMATE_DATA["all_country_positions"],
        },
    )


@app.get("/app/full", response_class=HTMLResponse)
async def app_page_full(request: Request, country: str = store.DEFAULT_COUNTRY, compare: str = ""):
    """v2: everything v1 has, plus product heatmaps, ranked top/bottom-10
    bars, tail-risk analysis, and the power generation Sankey -- every
    chart type the original notebook actually built.
    """
    country, country_data = store_v2.get_country_v2(country)
    compare = store.resolve_compare(country, compare)
    compare_data = store_v2.CLIMATE_DATA_V2["countries"][compare] if compare else None

    insights = {
        key: store_v2.build_indicator_insight_v2(
            country, ind, compare,
            compare_data["indicators"].get(key) if compare_data else None,
        )
        for key, ind in country_data["indicators"].items()
    }
    action_summary = store_v2.build_action_summary_v2(country, country_data, compare, compare_data)

    ranked = {
        key: store_v2.ranked_products(country_data, key)
        for key in ["crop_yield", "livestock_yield"]
    }
    ranked_insights = {
        key: (
            store_v2.ranked_products_insight(country, country_data["indicators"][key]["label"], country_data["indicators"][key]["unit"], ranked[key])
            if key in country_data["indicators"]
            else f"No {key.replace('_', ' ')} data is available for {country}."
        )
        for key in ranked
    }
    # Per-chart insight for the split Top-10 / Bottom-10 charts (previously
    # these charts had no accompanying insight text at all).
    ranked_split_insights = {
        f"{key}_{which}": (
            store_v2.ranked_single_insight(country, country_data["indicators"][key]["label"], country_data["indicators"][key]["unit"], ranked[key][which], which)
            if key in country_data["indicators"]
            else f"No {key.replace('_', ' ')} data is available for {country}."
        )
        for key in ranked
        for which in ["top", "bottom"]
    }
    compare_ranked = None
    compare_ranked_insights = None
    compare_ranked_split_insights = None
    if compare_data:
        compare_ranked = {key: store_v2.ranked_products(compare_data, key) for key in ["crop_yield", "livestock_yield"]}
        compare_ranked_insights = {
            key: (
                store_v2.ranked_products_insight(compare, compare_data["indicators"][key]["label"], compare_data["indicators"][key]["unit"], compare_ranked[key])
                if key in compare_data["indicators"]
                else f"No {key.replace('_', ' ')} data is available for {compare}."
            )
            for key in compare_ranked
        }
        compare_ranked_split_insights = {
            f"{key}_{which}": (
                store_v2.ranked_single_insight(compare, compare_data["indicators"][key]["label"], compare_data["indicators"][key]["unit"], compare_ranked[key][which], which)
                if key in compare_data["indicators"]
                else f"No {key.replace('_', ' ')} data is available for {compare}."
            )
            for key in compare_ranked
            for which in ["top", "bottom"]
        }

    tail_risk_insights = {
        key: store_v2.tail_risk_insight(country, country_data["indicators"][key]["label"], country_data["indicators"][key]["unit"], country_data["tail_risk"][key])
        for key in country_data["tail_risk"]
    }

    power_source_insight = store_v2.power_source_insight(country, country_data["power_sources"])
    compare_power_source_insight = (
        store_v2.power_source_insight(compare, compare_data["power_sources"]) if compare_data else None
    )
    sankey_insight = store_v2.sankey_insight(country, country_data["power_sankey"])
    compare_sankey_insight = store_v2.sankey_insight(compare, compare_data["power_sankey"]) if compare_data else None

    chart_payload = store.build_chart_payload(country, country_data, compare)
    v2_payload = {
        "primary": {
            "name": country,
            "products": country_data["products"],
            "power_sources": country_data["power_sources"],
            "power_sankey": country_data["power_sankey"],
            "tail_risk": country_data["tail_risk"],
            "ranked": ranked,
        },
        "compare": (
            {
                "name": compare,
                "products": compare_data["products"],
                "power_sources": compare_data["power_sources"],
                "power_sankey": compare_data["power_sankey"],
                "tail_risk": compare_data["tail_risk"],
                "ranked": compare_ranked,
            }
            if compare_data else None
        ),
    }

    return templates.TemplateResponse(
        request,
        "app_full.html",
        {
            "country_names": store.COUNTRY_NAMES,
            "selected_country": country,
            "compare_country": compare,
            "country_data": country_data,
            "chapters": store.CLIMATE_DATA["chapters"],
            "insights": insights,
            "action_summary": action_summary,
            "ranked_insights": ranked_insights,
            "compare_ranked_insights": compare_ranked_insights,
            "ranked_split_insights": ranked_split_insights,
            "compare_ranked_split_insights": compare_ranked_split_insights,
            "tail_risk_insights": tail_risk_insights,
            "power_source_insight": power_source_insight,
            "compare_power_source_insight": compare_power_source_insight,
            "sankey_insight": sankey_insight,
            "compare_sankey_insight": compare_sankey_insight,
            "chart_payload": chart_payload,
            "v2_payload": v2_payload,
            "all_country_positions": store.CLIMATE_DATA["all_country_positions"],
        },
    )


class ActionPlanRequest(BaseModel):
    country: str
    summary: str

@app.post("/api/action-plan")
async def generate_action_plan(payload: ActionPlanRequest):
    """Sends the dynamic trend summary to Airia AI and returns its markdown
    response. 
    """
    api_url = 'https://api.airia.ai/v2/PipelineExecution/0c6dd785-b1f2-42a4-8637-d81560f4b0a5'
    api_key = os.environ.get("AIRIA_API_KEY")

    if not api_url or not api_key:
        return JSONResponse(
            status_code=501,
            content={
                "error": (
                    "Airia AI isn't configured yet. Check AIRIA_API_KEY environment variable."
                )
            },
        )

    prompt = (
        f"You are a climate change expert and advisor for {payload.country}.\n\n"
        f"Based on this data summary:\n"
        f"\"\"\"\n{payload.summary}\n\"\"\"\n\n"
        f"Write a short, concrete climate action plan in markdown, "
        f"organized by theme (Land & Food, Ocean & Atmosphere, People & Economy)."
    )

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            api_url,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            },
            json={
                "userInput": prompt,
                "asyncOutput": False
            },  
        )
        
        # Prevent unhandled exceptions and pass the exact error back to the frontend
        if not response.is_success:
            return JSONResponse(
                status_code=500,
                content={
                    "error": f"Airia API Error {response.status_code}: {response.text}"
                }
            )

        data = response.json()

    # Parse the nested JSON string Airia sends back in the 'result' key
    result_str = data.get("result")
    markdown_text = ""

    if result_str:
        try:
            # Parse the inner JSON string
            inner_data = json.loads(result_str)
            # Extract the actual markdown content
            markdown_text = inner_data.get("output_info", "")
        except json.JSONDecodeError:
            # Fallback if Airia ever changes their response format to raw string
            markdown_text = result_str
    else:
        # Ultimate fallback if the 'result' key is completely missing
        markdown_text = str(data)

    return {"markdown": markdown_text}


@app.exception_handler(404)
async def custom_404_handler(request: Request, _exc):
    return templates.TemplateResponse(request, "404.html", status_code=404)


@app.exception_handler(500)
async def custom_500_handler(request: Request, _exc):
    return templates.TemplateResponse(request, "500.html", status_code=500)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Catches anything that isn't an explicit HTTPException (e.g. a KeyError
    print(f"Unhandled exception on {request.url}: {exc!r}")
    return templates.TemplateResponse(request, "500.html", status_code=500)
