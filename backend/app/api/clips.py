"""Clip routes: read, update trim points, export one clip."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user, to_user_error
from ..models import Clip, Export
from ..schemas import ClipResponse, ClipUpdateRequest, ExportRequest, ExportResponse
from ..services import video_service
from ..workers.jobs import submit_job

router = APIRouter()


def _to_response(clip: Clip) -> ClipResponse:
    thumb = ""
    if clip.thumbnail_path:
        thumb = f"/api/files/thumbnails/{Path(clip.thumbnail_path).name}"
    return ClipResponse(
        id=clip.id,
        video_id=clip.video_id,
        rank=clip.rank,
        start_time=clip.start_time,
        end_time=clip.end_time,
        duration=clip.duration,
        score=clip.score,
        reasons=list(clip.reasons or []),
        signals=dict(clip.signals or {}),
        title=clip.title or "",
        thumbnail_url=thumb,
        status=clip.status,
    )


def _get_clip(db: Session, clip_id: str) -> Clip:
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found.")
    return clip


@router.get("/clips/{clip_id}", response_model=ClipResponse)
def get_clip(clip_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _to_response(_get_clip(db, clip_id))


@router.put("/clips/{clip_id}", response_model=ClipResponse)
def update_clip(
    clip_id: str,
    body: ClipUpdateRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    settings = get_settings()
    clip = _get_clip(db, clip_id)
    video = video_service.get_video_or_404(db, clip.video_id)
    try:
        start = body.start_time if body.start_time is not None else clip.start_time
        end = body.end_time if body.end_time is not None else clip.end_time
        start = max(0.0, min(float(start), video.duration))
        end = max(0.0, min(float(end), video.duration))
        if end <= start:
            raise HTTPException(status_code=400, detail="Clip end must be after clip start.")
        if end - start < 1.0:
            raise HTTPException(status_code=400, detail="Clip must be at least 1 second long.")
        if end - start > settings.max_clip_duration:
            raise HTTPException(
                status_code=400,
                detail=f"Clip is too long. Maximum is {settings.max_clip_duration:.0f}s.",
            )
        clip.start_time = round(start, 2)
        clip.end_time = round(end, 2)
        clip.duration = round(end - start, 2)
        if body.title is not None:
            clip.title = body.title[:256]
        # Manual trims invalidate old "exported" state for clarity.
        if clip.status == "exported":
            clip.status = "ready"
        db.commit()
        db.refresh(clip)
        return _to_response(clip)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.post("/clips/{clip_id}/export", response_model=ExportResponse, status_code=202)
def export_clip(
    clip_id: str,
    body: ExportRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    clip = _get_clip(db, clip_id)
    export = Export(
        clip_id=clip.id,
        video_id=clip.video_id,
        aspect_ratio=body.aspect_ratio,
        output_format=body.output_format,
        quality=body.quality,
        status="queued",
    )
    db.add(export)
    db.flush()
    clip.status = "exporting"
    db.commit()
    db.refresh(export)
    submit_job("export", clip.video_id, {"export_id": export.id})
    return ExportResponse(
        id=export.id,
        clip_id=export.clip_id,
        video_id=export.video_id,
        aspect_ratio=export.aspect_ratio,
        output_format=export.output_format,
        quality=export.quality,
        width=export.width,
        height=export.height,
        status=export.status,
        progress=export.progress,
        file_size=export.file_size,
        error_message="",
        download_url="",
        created_at=export.created_at,  # type: ignore[arg-type]
    )
