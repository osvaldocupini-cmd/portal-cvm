import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import b3_service, cache
from app.api.routes import data, export, metadata
from app.config import settings
from app.models.schemas import CacheRefreshResponse

STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_year = settings.MAX_YEAR
    logger.info("Preloading year %d on startup...", current_year)
    try:
        await cache.preload([current_year])
    except Exception as exc:
        logger.warning("Could not preload year %d on startup: %s", current_year, exc)
    try:
        await b3_service.load()
    except Exception as exc:
        logger.warning("Could not load B3 data on startup: %s", exc)
    yield


app = FastAPI(
    title="CVM Portal API",
    description="API para consulta de demonstracoes financeiras de empresas abertas brasileiras (DFP/CVM)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(metadata.router)
app.include_router(data.router)
app.include_router(export.router)


@app.post("/api/v1/cache/refresh", response_model=CacheRefreshResponse, tags=["admin"])
async def refresh_cache(year: int):
    """Force re-download and reprocessing of data for a specific year."""
    rows = await cache.invalidate(year)
    return CacheRefreshResponse(status="ok", rows_loaded=rows)


@app.get("/", tags=["health"])
async def root():
    """Serve the frontend HTML."""
    return FileResponse(STATIC_DIR / "index.html")
