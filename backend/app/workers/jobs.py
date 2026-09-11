"""Background job system.

Production path: Redis + RQ/Celery when USE_REDIS_QUEUE=true (integration
point documented in README). Default path: an in-process thread pool that
needs no extra infrastructure, so `uvicorn app.main:app` alone runs the full
pipeline. Jobs persist progress on the Video/Export rows for polling + SSE.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..config import get_settings
from ..db import get_session_factory
from ..models import Export, Video
from ..utils.logging import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class Job:
    id: str
    kind: str  # analyze | export | export_all
    video_id: str
    status: str = "queued"  # queued|running|completed|failed
    progress: float = 0.0
    message: str = ""
    error: str = ""
    payload: dict = field(default_factory=dict)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_pool: ThreadPoolExecutor | None = None


def _pool_or_create() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        workers = max(1, get_settings().worker_concurrency)
        _pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="clipforge")
    return _pool


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def _update(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            for k, v in fields.items():
                setattr(job, k, v)


def _fail_video(video_id: str, message: str) -> None:
    factory = get_session_factory()
    db = factory()
    try:
        video = db.get(Video, video_id)
        if video:
            video.status = "failed"
            video.error_message = message
            db.commit()
    finally:
        db.close()


def _run_analyze(job: Job) -> None:
    from ..services.analysis_pipeline import run_analysis  # deferred: avoids import cycles

    _update(job.id, status="running", message="Analysis started")
    factory = get_session_factory()
    db = factory()
    try:
        video = db.get(Video, job.video_id)

        def report(progress: float, stage: str, message: str) -> None:
            _update(job.id, progress=progress, message=message)
            try:
                v = db.get(Video, job.video_id)
                if v:
                    v.status = stage
                    v.progress = progress
                    v.stage_message = message
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("progress persist failed: %s", exc)
                db.rollback()

        if video:
            video.status = "analyzing"
            video.error_message = ""
            db.commit()
        run_analysis(
            db,
            job.video_id,
            float(job.payload.get("clip_duration", 30.0)),
            int(job.payload.get("num_clips", 10)),
            report,
        )
        _update(job.id, status="completed", progress=100.0, message="Analysis complete")
    except Exception as exc:  # noqa: BLE001 - jobs must never crash the pool
        logger.error("analyze job %s failed: %s\n%s", job.id, exc, traceback.format_exc())
        _update(job.id, status="failed", error=str(exc)[:500])
        _fail_video(job.video_id, _user_message(exc))
    finally:
        db.close()
        log_event(logger, "job_finished", job_id=job.id, kind="analyze", video_id=job.video_id)


def _run_export(job: Job) -> None:
    from ..services.export_service import render_export

    _update(job.id, status="running", message="Export started")
    factory = get_session_factory()
    db = factory()
    try:
        export = db.get(Export, job.payload["export_id"])
        if export is None:
            raise RuntimeError("Export not found.")
        render_export(db, export)
        _update(job.id, status="completed", progress=100.0, message="Export complete")
    except Exception as exc:  # noqa: BLE001
        logger.error("export job %s failed: %s\n%s", job.id, exc, traceback.format_exc())
        _update(job.id, status="failed", error=str(exc)[:500])
        try:
            export = db.get(Export, job.payload.get("export_id", ""))
            if export:
                export.status = "failed"
                export.error_message = _user_message(exc)
                db.commit()
        finally:
            pass
    finally:
        db.close()


def _run_export_all(job: Job) -> None:
    from ..services.export_service import render_export

    _update(job.id, status="running", message="Batch export started")
    factory = get_session_factory()
    db = factory()
    try:
        export_ids: list[str] = job.payload.get("export_ids", [])
        total = len(export_ids)
        for i, export_id in enumerate(export_ids, start=1):
            _update(job.id, progress=100.0 * (i - 1) / max(1, total), message=f"Exporting {i}/{total}")
            export = db.get(Export, export_id)
            if export is None:
                continue
            try:
                render_export(db, export)
            except Exception as exc:  # noqa: BLE001 - one failure must not stop the batch
                logger.warning("batch export item failed: %s", exc)
                export.status = "failed"
                export.error_message = _user_message(exc)
                db.commit()
        _update(job.id, status="completed", progress=100.0, message="Batch export complete")
    finally:
        db.close()


_RUNNERS = {"analyze": _run_analyze, "export": _run_export, "export_all": _run_export_all}


def submit_job(kind: str, video_id: str, payload: dict | None = None) -> Job:
    settings = get_settings()
    job = Job(id=uuid.uuid4().hex, kind=kind, video_id=video_id, payload=payload or {})
    with _lock:
        _jobs[job.id] = job
    log_event(logger, "job_submitted", job_id=job.id, kind=kind, video_id=video_id)
    if settings.use_redis_queue and settings.redis_url:
        # Redis/RQ integration point: enqueue {"job_id": job.id, ...} and let a
        # separate worker process call run_job(job.id). Falls back below when
        # redis is unreachable so uploads never hang.
        try:
            _enqueue_redis(job)
            return job
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis enqueue failed, using local pool: %s", exc)
    _pool_or_create().submit(_RUNNERS[kind], job)
    return job


def run_job(job_id: str) -> None:
    """Entry point for external (Redis) workers."""
    job = get_job(job_id)
    if job and job.kind in _RUNNERS:
        _RUNNERS[job.kind](job)


def _enqueue_redis(job: Job) -> None:
    import json as _json

    try:
        import redis  # type: ignore
    except ImportError as exc:
        raise RuntimeError("redis package not installed") from exc
    client = redis.Redis.from_url(get_settings().redis_url or "")
    client.rpush("clipforge:jobs", _json.dumps({"job_id": job.id}))
    _update(job.id, message="Queued in Redis")


def _user_message(exc: Exception) -> str:
    from ..utils.security import ValidationError

    if isinstance(exc, ValidationError):
        return str(exc)
    text = str(exc)
    if "Audio extraction failed" in text:
        return "We couldn't read this video's audio track. The file may be corrupted."
    if "Export failed" in text or "ffmpeg" in text.lower():
        return "Video rendering failed. Please try another clip or quality setting."
    if "timed out" in text.lower():
        return "Processing timed out. Please try a shorter video."
    return "We couldn't process this video. Please try another video or check that the file isn't corrupted."
