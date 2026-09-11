"""Single-process frontend hosting: built SPA + client-side-route fallback.

The multi-stage Dockerfile builds ``frontend/dist`` and bakes it into the API
image, so one container/one port serves the whole app. Plain
``StaticFiles(html=True)`` is not enough: React Router owns paths like
``/editor/:id`` that have no file on disk, so they would 404 on refresh or on a
cold deep link. ``SPAStaticFiles`` answers those with ``index.html`` while still
serving real files (hashed JS/CSS bundles, images, the favicon) directly and
keeping ``/api/*`` a JSON 404 so API clients never parse HTML by mistake.
"""

from __future__ import annotations

from pathlib import Path

import anyio.to_thread
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from .logging import get_logger

logger = get_logger(__name__)

# Vite fingerprints everything under /assets, so those can be cached forever.
_IMMUTABLE = "public, max-age=31536000, immutable"
_NO_CACHE = "no-cache"


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to ``index.html`` for unknown GET routes."""

    def __init__(self, *, directory: Path | str, index: str = "index.html") -> None:
        super().__init__(directory=str(directory), html=False)
        self.index_file = index

    async def get_response(self, path: str, scope) -> Response:  # type: ignore[override]
        if scope.get("method", "GET").upper() not in ("GET", "HEAD"):
            raise HTTPException(status_code=405)

        clean = (path or ".").strip("/")
        if clean == ".":
            clean = ""

        # API routes are matched by the app router first; anything still asking
        # the frontend for /api/... is a genuine 404 and must stay JSON.
        if clean == "api" or clean.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        if clean in ("", self.index_file):
            return await self._index_response(scope)

        try:
            response = await super().get_response(clean, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            # Client-side route (or a deleted asset) -> let React handle it.
            return await self._index_response(scope)
        if response.status_code == 404:  # older Starlette returns instead of raising
            return await self._index_response(scope)

        response.headers.setdefault(
            "Cache-Control", _IMMUTABLE if clean.startswith("assets/") else _NO_CACHE
        )
        return response

    async def _index_response(self, scope) -> Response:
        full_path, stat_result = await anyio.to_thread.run_sync(self.lookup_path, self.index_file)
        if stat_result is None:
            raise HTTPException(status_code=404, detail="Frontend build not found.")
        # Re-read every request so a new deploy is picked up without a restart.
        response = self.file_response(full_path, stat_result, scope)
        response.headers["Cache-Control"] = _NO_CACHE
        return response


def mount_frontend(app: FastAPI, dist: Path | str | None) -> bool:
    """Serve ``dist`` at ``/`` with SPA fallback. Returns True when mounted."""
    if not dist:
        logger.info(
            "no frontend build found; serving API only (run `npm run build` or set FRONTEND_DIST)"
        )
        return False
    root = Path(dist)
    if not (root / "index.html").is_file():
        logger.warning("frontend dist %s has no index.html; serving API only", root)
        return False
    app.mount("/", SPAStaticFiles(directory=root), name="frontend")
    logger.info("serving frontend from %s", root)
    return True
