"""Export routes: status polling + file download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Export
from ..schemas import ExportResponse

router = APIRouter()


def _to_response(exp: Export) -> ExportResponse:
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


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export(export_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    exp = db.get(Export, export_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    return _to_response(exp)


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db)):
    exp = db.get(Export, export_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    if exp.status != "completed" or not exp.output_path:
        raise HTTPException(status_code=409, detail="Export is not ready yet.")
    path = Path(exp.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file no longer available.")
    ext = "webm" if exp.output_format == "webm" else "mp4"
    media = "video/webm" if ext == "webm" else "video/mp4"
    return FileResponse(path, media_type=media, filename=f"clipforge_{exp.clip_id[:8]}.{ext}")
