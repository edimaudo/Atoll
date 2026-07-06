from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(title="Pacific Island & Territories Climate Change")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the landing page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    """Main app page"""
    return templates.TemplateResponse("app.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """Talks about the challenge and data."""
    return templates.TemplateResponse("about.html", {"request": request})

@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return HTMLResponse(str(exc.detail), status_code=exc.status_code)
