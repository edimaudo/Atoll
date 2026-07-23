import os
from pathlib import Path
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import store

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Atoll — Pacific Climate Change")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Hook, how-to-navigate, datasets used, one CTA into the app."""
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
        key: store.build_indicator_insight(
            country, ind, compare,
            compare_data["indicators"].get(key) if compare_data else None,
        )
        for key, ind in country_data["indicators"].items()
    }

    action_summary = store.build_action_summary(country, country_data, compare, compare_data)

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
    import store_v2

    country, country_data = store_v2.get_country_v2(country)
    compare = store.resolve_compare(country, compare)
    compare_data = store_v2.CLIMATE_DATA_V2["countries"][compare] if compare else None

    insights = {
        key: store.build_indicator_insight(
            country, ind, compare,
            compare_data["indicators"].get(key) if compare_data else None,
        )
        for key, ind in country_data["indicators"].items()
    }
    action_summary = store.build_action_summary(country, country_data, compare, compare_data)

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
    compare_ranked = None
    compare_ranked_insights = None
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
    api_url = os.environ.get("API_URL")
    api_key = os.environ.get("API_KEY")

    if not api_url or not api_key:
        return JSONResponse(
            status_code=501,
            content={
                "error": (
                    "Airia AI isn't configured yet. Check AIRIA_API_URL and AIRIA_API_KEY "
                )
            },
        )

    prompt = (
        f"You are a climate adaptation advisor. Based on this data summary for "
        f"{payload.country}, write a short, concrete climate action plan in "
        f"markdown, organized by theme (Land & Food, Ocean & Atmosphere, "
        f"People & Economy):\n\n{payload.summary}"
    )

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": prompt},  
        )
        response.raise_for_status()
        data = response.json()

    # TODO: adjust to however Airia's response actually nests the markdown text
    markdown = data.get("output") or data.get("text") or str(data)
    return {"markdown": markdown}


@app.exception_handler(404)
async def custom_404_handler(request: Request, _exc):
    return templates.TemplateResponse(request, "404.html", status_code=404)


@app.exception_handler(500)
async def custom_500_handler(request: Request, _exc):
    return templates.TemplateResponse(request, "500.html", status_code=500)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Catches anything that isn't an explicit HTTPException (e.g. a KeyError
    # from a data gap we didn't anticipate) so a real user sees a friendly
    # page instead of a raw traceback. Logged server-side either way.
    print(f"Unhandled exception on {request.url}: {exc!r}")
    return templates.TemplateResponse(request, "500.html", status_code=500)
