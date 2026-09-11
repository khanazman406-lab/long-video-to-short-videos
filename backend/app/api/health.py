"""GET /api/health — liveness + dependency checks (no secrets exposed)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..config import get_settings
from ..db import get_engine
from ..schemas import HealthResponse
from ..services import ffmpeg_service
from ..services.transcript_service import get_transcript_analyzer

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        database = True
    except Exception:
        database = False
    analyzer = get_transcript_analyzer()
    return HealthResponse(
        status="ok" if database else "degraded",
        app=settings.app_name,
        ffmpeg=ffmpeg_service.ffmpeg_available(),
        database=database,
        queue=True,  # local pool always available; redis optional
        transcript_engine=analyzer.name if analyzer.available else "disabled",
    )
