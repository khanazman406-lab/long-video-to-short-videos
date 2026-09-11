"""Export orchestration: face-aware auto-reframe + ffmpeg rendering."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Clip, Export, Video
from ..utils.logging import get_logger
from . import ffmpeg_service
from .face_detector import HaarFaceDetector

logger = get_logger(__name__)

# Reuse one detector instance for reframe lookups (cascade load is slowish).
_face_detector: HaarFaceDetector | None = None


def _detector() -> HaarFaceDetector:
    global _face_detector
    if _face_detector is None:
        _face_detector = HaarFaceDetector()
    return _face_detector


def compute_reframe_focus(video_path: str, start: float, end: float, aspect: str) -> tuple[float, float]:
    """Pick a crop center. For 9:16/1:1, track the dominant face (v1 auto-reframe).

    Falls back to frame center when no face is found. 16:9 keeps full frame.
    """
    if aspect == "16:9":
        return 0.5, 0.5
    try:
        # Observe a few seconds around the clip for faces (cheap, 1 fps).
        det = _detector()
        mid_start = max(0.0, start - 2.0)
        mid_end = end + 2.0
        observations = det.detect(video_path, mid_end)
        windowed = [o for o in observations if mid_start <= o.time <= mid_end]
        fx = det.dominant_face_center(windowed, mid_start, mid_end)
        if fx is not None:
            return float(fx), 0.45  # faces sit slightly above center
    except Exception as exc:  # noqa: BLE001 - reframe must not break export
        logger.warning("reframe fallback to center: %s", exc)
    return 0.5, 0.5


def render_export(db: Session, export: Export) -> Export:
    settings = get_settings()
    clip = db.get(Clip, export.clip_id)
    if clip is None:
        raise RuntimeError("Clip not found for export.")
    video = db.get(Video, clip.video_id)
    if video is None:
        raise RuntimeError("Source video not found for export.")

    export.status = "exporting"
    export.progress = 5.0
    db.commit()

    focus_x, focus_y = compute_reframe_focus(
        video.storage_path, clip.start_time, clip.end_time, export.aspect_ratio
    )
    ext = "webm" if export.output_format == "webm" else "mp4"
    out_path = settings.data_dir / "exports" / f"{export.id}.{ext}"

    target_w, target_h = ffmpeg_service.ASPECT_TARGETS.get(
        export.aspect_ratio, ffmpeg_service.ASPECT_TARGETS["16:9"]
    )
    export.width, export.height = target_w, target_h
    export.progress = 15.0
    db.commit()

    ffmpeg_service.export_clip(
        video.storage_path,
        out_path,
        clip.start_time,
        clip.end_time,
        aspect=export.aspect_ratio,
        output_format=export.output_format,
        quality=export.quality,
        src_w=video.width,
        src_h=video.height,
        focus_x=focus_x,
        focus_y=focus_y,
    )
    export.output_path = str(out_path)
    export.file_size = Path(out_path).stat().st_size
    export.status = "completed"
    export.progress = 100.0
    clip.status = "exported"
    db.commit()
    db.refresh(export)
    logger.info("export completed: %s (%d bytes)", export.id, export.file_size)
    return export
