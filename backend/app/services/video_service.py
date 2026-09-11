"""Upload validation + video record management."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Video
from ..utils.logging import get_logger, log_event
from ..utils.security import ValidationError, sanitize_filename
from . import ffmpeg_service
from .storage import get_storage

logger = get_logger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB streaming chunks


class VideoValidator:
    def __init__(self):
        self.settings = get_settings()

    def validate_extension(self, filename: str) -> str:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in self.settings.allowed_extension_list():
            raise ValidationError(
                f"Unsupported video format '.{ext or '?'}'. "
                f"Supported: {', '.join(self.settings.allowed_extension_list())}."
            )
        return ext

    def validate_mime(self, mime: str | None) -> None:
        if not mime:
            return
        if mime.lower() not in self.settings.allowed_mime_list():
            # MIME types from browsers are hints, not ground truth — only warn.
            logger.warning("unexpected mime type upload: %s", mime)

    def validate_size(self, size: int) -> None:
        if size <= 0:
            raise ValidationError("Uploaded file is empty.")
        if size > self.settings.max_upload_size:
            gb = self.settings.max_upload_size / (1024**3)
            raise ValidationError(f"Video is too large. Maximum size is {gb:.1f} GB.")

    def validate_duration(self, duration: float) -> None:
        if duration < self.settings.min_video_duration:
            raise ValidationError(
                f"Video is too short ({duration:.1f}s). Minimum is {self.settings.min_video_duration:.0f}s."
            )
        if duration > self.settings.max_video_duration:
            raise ValidationError(
                f"Video is too long. Maximum duration is {self.settings.max_video_duration / 3600:.1f} hours."
            )


async def save_upload_stream(*, file, original_filename: str) -> tuple[Path, int, str]:
    """Stream an UploadFile to a temp path without loading it into memory."""
    settings = get_settings()
    validator = VideoValidator()
    ext = validator.validate_extension(original_filename)
    validator.validate_mime(getattr(file, "content_type", None))

    safe_name = sanitize_filename(original_filename)
    temp_name = f"upload_{uuid.uuid4().hex}.{ext}"
    temp_path = settings.data_dir / "temp" / temp_name
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    with open(temp_path, "wb") as out:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_size:
                out.close()
                temp_path.unlink(missing_ok=True)
                raise ValidationError("Video is too large.")
            out.write(chunk)
    validator.validate_size(size)
    log_event(logger, "upload_saved", temp=str(temp_path), size=size, filename=safe_name)
    return temp_path, size, safe_name


def finalize_upload(
    db: Session,
    *,
    temp_path: Path,
    original_filename: str,
    size: int,
    mime_type: str,
) -> Video:
    """Probe + validate the uploaded file, then create the Video record."""
    settings = get_settings()
    validator = VideoValidator()
    storage = get_storage()

    try:
        meta = ffmpeg_service.probe_video(temp_path)
    except ValidationError:
        temp_path.unlink(missing_ok=True)
        raise
    except RuntimeError as exc:
        temp_path.unlink(missing_ok=True)
        raise ValidationError("Video could not be decoded. The file may be corrupted.") from exc

    validator.validate_duration(meta.duration)

    stored_name = f"{uuid.uuid4().hex}_{sanitize_filename(original_filename)}"
    final_path = storage.save_upload(temp_path, stored_name)

    video = Video(
        filename=stored_name,
        original_filename=sanitize_filename(original_filename),
        storage_path=str(final_path),
        file_size=size,
        mime_type=mime_type or "",
        duration=meta.duration,
        width=meta.width,
        height=meta.height,
        fps=meta.fps,
        video_codec=meta.video_codec,
        audio_codec=meta.audio_codec,
        status="uploading",
        progress=100.0,
        stage_message="Upload complete",
        video_metadata={"has_audio": meta.has_audio, "has_video": meta.has_video},
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Best-effort poster thumbnail (never fails the upload).
    try:
        thumb = settings.data_dir / "thumbnails" / f"{video.id}.jpg"
        ffmpeg_service.extract_thumbnail(final_path, thumb, min(1.0, meta.duration / 3))
        video.thumbnail_path = str(thumb)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - thumbnail is non-critical
        logger.warning("thumbnail failed for %s: %s", video.id, exc)

    log_event(
        logger,
        "video_finalized",
        video_id=video.id,
        duration=meta.duration,
        resolution=f"{meta.width}x{meta.height}",
    )
    return video


def get_video_or_404(db: Session, video_id: str) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise ValidationError("Video not found.")
    return video
