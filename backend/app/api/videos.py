"""Video routes: upload, analyze, status, clips, streaming, SSE progress."""

from __future__ import annotations

import asyncio
import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, get_session_factory
from ..deps import get_current_user, to_user_error
from ..models import Clip, Export, Video
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ClipListResponse,
    ClipResponse,
    ExportAllRequest,
    ExportListResponse,
    ExportResponse,
    VideoResponse,
    VideoStatusResponse,
)
from ..services import video_service
from ..utils.logging import get_logger
from ..workers.jobs import get_job, submit_job

logger = get_logger(__name__)
router = APIRouter()


def _thumb_url(path: str) -> str:
    if not path:
        return ""
    name = Path(path).name
    return f"/api/files/thumbnails/{name}"


def _video_to_response(video: Video, num_clips: int = 0) -> VideoResponse:
    return VideoResponse(
        id=video.id,
        filename=video.filename,
        original_filename=video.original_filename,
        file_size=video.file_size,
        mime_type=video.mime_type,
        duration=video.duration,
        width=video.width,
        height=video.height,
        fps=video.fps,
        video_codec=video.video_codec,
        audio_codec=video.audio_codec,
        status=video.status,
        progress=video.progress,
        stage_message=video.stage_message,
        error_message=video.error_message or "",
        thumbnail_url=_thumb_url(video.thumbnail_path or ""),
        num_clips=num_clips,
        created_at=video.created_at,  # type: ignore[arg-type]
    )


def _clip_to_response(clip: Clip) -> ClipResponse:
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
        thumbnail_url=_thumb_url(clip.thumbnail_path or ""),
        status=clip.status,
    )


@router.get("/videos", response_model=list[VideoResponse])
def list_videos(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    videos = db.query(Video).order_by(Video.created_at.desc()).limit(50).all()
    out = []
    for v in videos:
        n = db.query(Clip).filter(Clip.video_id == v.id).count()
        out.append(_video_to_response(v, n))
    return out


@router.post("/videos/upload", response_model=VideoResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    try:
        temp_path, size, _safe = await video_service.save_upload_stream(
            file=file, original_filename=file.filename or "video.mp4"
        )
        video = video_service.finalize_upload(
            db,
            temp_path=temp_path,
            original_filename=file.filename or "video.mp4",
            size=size,
            mime_type=file.content_type or mimetypes.guess_type(file.filename or "")[0] or "",
        )
        return _video_to_response(video, 0)
    except Exception as exc:  # noqa: BLE001 - mapped to friendly errors below
        status, message = to_user_error(exc)
        logger.warning("upload failed: %s", message)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    try:
        video = video_service.get_video_or_404(db, video_id)
        n = db.query(Clip).filter(Clip.video_id == video.id).count()
        return _video_to_response(video, n)
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.delete("/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    from ..services.storage import get_storage

    try:
        video = video_service.get_video_or_404(db, video_id)
        storage = get_storage()
        paths = [video.storage_path, video.thumbnail_path]
        for clip in video.clips:
            paths.append(clip.thumbnail_path)
            for exp in clip.exports:
                paths.append(exp.output_path)
        db.delete(video)
        db.commit()
        for p in paths:
            if p:
                storage.delete(Path(p))
        return {"deleted": video_id}
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.post("/videos/{video_id}/analyze", response_model=AnalyzeResponse, status_code=202)
def analyze_video(
    video_id: str,
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    try:
        settings = get_settings()
        video = video_service.get_video_or_404(db, video_id)
        clip_duration = min(max(body.clip_duration, settings.min_clip_duration), settings.max_clip_duration)
        num_clips = max(1, min(body.num_clips, settings.max_num_clips))
        video.status = "queued"
        video.progress = 0.0
        video.stage_message = "Queued for analysis…"
        video.error_message = ""
        db.commit()
        job = submit_job(
            "analyze",
            video.id,
            {"clip_duration": clip_duration, "num_clips": num_clips},
        )
        return AnalyzeResponse(
            video_id=video.id, job_id=job.id, status="queued", message="Analysis started."
        )
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/videos/{video_id}/status", response_model=VideoStatusResponse)
def video_status(video_id: str, db: Session = Depends(get_db)):
    try:
        video = video_service.get_video_or_404(db, video_id)
        n = db.query(Clip).filter(Clip.video_id == video.id).count()
        return VideoStatusResponse(
            id=video.id,
            status=video.status,
            progress=video.progress,
            stage_message=video.stage_message or "",
            error_message=video.error_message or "",
            num_clips=n,
        )
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/videos/{video_id}/events")
async def video_events(video_id: str):
    """Server-Sent Events progress stream (frontend falls back to polling)."""

    async def gen():
        factory = get_session_factory()
        last = ""
        # Stream for up to ~30 min; client reconnects if needed.
        for _ in range(1800):
            db = factory()
            try:
                video = db.get(Video, video_id)
                if video is None:
                    yield 'event: error\ndata: {"detail": "Video not found."}\n\n'
                    return
                payload = (
                    f'{{"status": "{video.status}", "progress": {video.progress:.1f}, '
                    f'"stage_message": "{(video.stage_message or "").replace(chr(34), chr(39))}", '
                    f'"error_message": "{(video.error_message or "").replace(chr(34), chr(39))}"}}'
                )
                if payload != last:
                    yield f"data: {payload}\n\n"
                    last = payload
                if video.status in ("completed", "failed"):
                    return
            finally:
                db.close()
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/videos/{video_id}/clips", response_model=ClipListResponse)
def list_clips(video_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    try:
        video = video_service.get_video_or_404(db, video_id)
        clips = db.query(Clip).filter(Clip.video_id == video.id).order_by(Clip.rank).all()
        return ClipListResponse(
            video_id=video.id, count=len(clips), clips=[_clip_to_response(c) for c in clips]
        )
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: str, request: Request, db: Session = Depends(get_db)):
    """Range-capable video streaming so players can seek."""
    try:
        video = video_service.get_video_or_404(db, video_id)
        path = Path(video.storage_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Video file no longer available.")
        return _range_response(path, request)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "id": job.id,
        "kind": job.kind,
        "video_id": job.video_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
    }


@router.post("/videos/{video_id}/export-all", response_model=ExportListResponse, status_code=202)
def export_all(
    video_id: str,
    body: ExportAllRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    try:
        video = video_service.get_video_or_404(db, video_id)
        query = db.query(Clip).filter(Clip.video_id == video.id)
        if body.clip_ids:
            query = query.filter(Clip.id.in_(body.clip_ids))
        clips = query.order_by(Clip.rank).all()
        if not clips:
            raise HTTPException(status_code=400, detail="No clips to export.")
        exports: list[Export] = []
        for clip in clips:
            exp = Export(
                clip_id=clip.id,
                video_id=video.id,
                aspect_ratio=body.aspect_ratio,
                output_format=body.output_format,
                quality=body.quality,
                status="queued",
            )
            db.add(exp)
            db.flush()
            exports.append(exp)
            clip.status = "exporting"
        db.commit()
        submit_job("export_all", video.id, {"export_ids": [e.id for e in exports]})
        return ExportListResponse(
            video_id=video.id,
            count=len(exports),
            exports=[_export_to_response(e) for e in exports],
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


@router.get("/videos/{video_id}/exports", response_model=ExportListResponse)
def list_exports(video_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    try:
        video = video_service.get_video_or_404(db, video_id)
        exports = (
            db.query(Export).filter(Export.video_id == video.id).order_by(Export.created_at).all()
        )
        return ExportListResponse(
            video_id=video.id,
            count=len(exports),
            exports=[_export_to_response(e) for e in exports],
        )
    except Exception as exc:  # noqa: BLE001
        status, message = to_user_error(exc)
        raise HTTPException(status_code=status, detail=message) from exc


def _export_to_response(exp: Export) -> ExportResponse:
    return ExportResponse(
        id=exp.id,
        clip_id=exp.clip_id,
        video_id=exp.video_id,
        aspect_ratio=exp.aspect_ratio,
        output_format=exp.output_format,
        quality=exp.quality,
        width=exp.width,
        height=exp.height,
        status=exp.status,
        progress=exp.progress,
        file_size=exp.file_size,
        error_message=exp.error_message or "",
        download_url=f"/api/exports/{exp.id}/download" if exp.status == "completed" else "",
        created_at=exp.created_at,  # type: ignore[arg-type]
    )


def _range_response(path: Path, request: Request):
    file_size = os.path.getsize(path)
    content_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type=content_type, filename=path.name)
    try:
        units, _, spec = range_header.partition("=")
        start_s, _, end_s = spec.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except ValueError:
        return FileResponse(path, media_type=content_type, filename=path.name)
    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    length = end - start + 1

    def iterator():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(iterator(), status_code=206, headers=headers, media_type=content_type)
