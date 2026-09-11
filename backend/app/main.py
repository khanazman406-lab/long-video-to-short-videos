"""ClipForge AI — FastAPI application entry point."""

from __future__ import annotations

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import clips, exports, health, videos
from .config import get_settings
from .db import init_db
from .utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        settings.ensure_data_dirs()
        init_db()
        logger.info("%s starting (data_dir=%s)", settings.app_name, settings.data_dir)
        yield

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_tagline,
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- lightweight in-memory rate limiting --------------------------------
    _hits: dict[str, list[float]] = defaultdict(list)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            now = time.time()
            key = request.client.host if request.client else "unknown"
            window = [t for t in _hits[key] if now - t < 60]
            window.append(now)
            _hits[key] = window
            if len(window) > settings.rate_limit_per_minute and request.method != "GET":
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down and try again."},
                )
        return await call_next(request)

    # -- friendly global error handler (never leak tracebacks) --------------
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # noqa: ARG001
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500, content={"detail": "Something went wrong. Please try again."}
        )

    # -- routes --------------------------------------------------------------
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(clips.router, prefix="/api", tags=["clips"])
    app.include_router(exports.router, prefix="/api", tags=["exports"])

    # Serve thumbnails + a safe file endpoint.
    data_dir = Path(settings.data_dir)

    @app.get("/api/files/thumbnails/{name}")
    def serve_thumbnail(name: str):
        safe = Path(name).name
        path = data_dir / "thumbnails" / safe
        if not path.exists():
            return JSONResponse(status_code=404, content={"detail": "Thumbnail not found."})
        return FileResponse(path, media_type="image/jpeg")

    # Serve the built frontend when it exists (single-process deployment).
    dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    frontend_dist = Path(data_dir).parent / "frontend_dist"
    for candidate in (dist, frontend_dist):
        if candidate.exists():
            app.mount("/", StaticFiles(directory=candidate, html=True), name="frontend")
            break

    return app


app = create_app()
