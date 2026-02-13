import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.api.routes import router
from app.db.init_db import init_db

# Initialize DB (Creates app.db if missing)
init_db()

app = FastAPI(title=settings.PROJECT_NAME)

# Mounts
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/videos", StaticFiles(directory=settings.OUTPUT_DIR), name="videos")

# Templates
templates = Jinja2Templates(directory="app/templates")

# API Router
app.include_router(router, prefix="/api/v1")

# --- WEB PAGE ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/create", response_class=HTMLResponse)
async def create_page(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})

@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(request: Request):
    return templates.TemplateResponse("gallery.html", {"request": request})

@app.get("/database", response_class=HTMLResponse)
async def database_page(request: Request):
    return templates.TemplateResponse("database.html", {"request": request})

if __name__ == "__main__":
    print(f"🚀 FOUNDRY PRO IS LIVE | http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)