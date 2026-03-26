from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.logger import setup_logging
from app.services.vertex_service import init_vertex

setup_logging()

_WEB_DIR = Path(__file__).resolve().parents[1] / "web"
_EXPORTS_DIR = Path(__file__).resolve().parents[1] / "exports"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_vertex()
    yield


app = FastAPI(
    title="fast-video",
    description="AI video generation service powered by Google Vertex AI (Veo).",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)

# Static assets — must be mounted AFTER API routes to avoid shadowing them.
_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(_EXPORTS_DIR)), name="exports")
app.mount("/js",  StaticFiles(directory=str(_WEB_DIR / "js")),  name="js")
app.mount("/css", StaticFiles(directory=str(_WEB_DIR / "css")), name="css")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(str(_WEB_DIR / "index.html"))
