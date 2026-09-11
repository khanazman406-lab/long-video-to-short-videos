"""End-to-end analysis pipeline: video -> detectors -> scoring -> clips.

Stage flow: extracting -> analyzing -> scoring -> generating_clips ->
completed. Progress is reported through a callback so the job layer can
persist it for polling/SSE. Every detector is interface-swappable.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Clip, Video
from ..utils.logging import get_logger, log_event
from ..utils.timecode import format_range
from . import ffmpeg_service
from .audio_analyzer import EnergyAudioAnalyzer
from .clip_generator import select_top_clips
from .engagement_scorer import WeightedEngagementScorer
from .face_detector import HaarFaceDetector
from .motion_analyzer import FrameDiffMotionAnalyzer
from .scene_detector import HistogramSceneDetector
from .transcript_service import get_transcript_analyzer

logger = get_logger(__name__)

ProgressCb = Callable[[float, str, str], None]  # (progress, stage, message)


def run_analysis(
    db: Session,
    video_id: str,
    clip_duration: float,
    num_clips: int,
    report: ProgressCb,
) -> list[Clip]:
    settings = get_settings()
    video = db.get(Video, video_id)
    if video is None:
        raise RuntimeError("Video not found.")
    video_path = video.storage_path
    duration = video.duration
    if duration <= 0:
        meta = ffmpeg_service.probe_video(video_path)
        duration = meta.duration
        video.duration = duration
        db.commit()

    log_event(logger, "analysis_started", video_id=video_id, duration=duration)

    # -- extracting (thumbnails / warm-up) ---------------------------------
    report(5, "extracting", "Preparing video for analysis…")

    # -- analyzing ----------------------------------------------------------
    report(12, "analyzing", "Analyzing audio energy and speech…")
    audio = EnergyAudioAnalyzer().analyze(video_path, duration)

    report(32, "analyzing", "Detecting scenes and cuts…")
    scenes = HistogramSceneDetector().detect(video_path, duration)

    report(52, "analyzing", "Tracking faces…")
    faces = HaarFaceDetector().detect(video_path, duration)

    report(66, "analyzing", "Measuring motion…")
    motion = FrameDiffMotionAnalyzer().analyze(video_path, duration)

    report(76, "analyzing", "Transcribing speech (optional)…")
    transcripts = get_transcript_analyzer().transcribe(video_path, duration)

    # -- scoring -------------------------------------------------------------
    report(84, "scoring", "Scoring engagement moments…")
    scorer = WeightedEngagementScorer()
    scored_windows = scorer.score_windows(duration, 1.0, audio, scenes, faces, motion, transcripts)

    # -- generating clips ----------------------------------------------------
    report(90, "generating_clips", "Selecting the best clips…")
    top = select_top_clips(duration, clip_duration, num_clips, scored_windows, audio, scenes, transcripts)

    # Replace previous clips for idempotent re-analysis.
    for old in list(video.clips):
        if old.thumbnail_path:
            Path(old.thumbnail_path).unlink(missing_ok=True)
        db.delete(old)
    db.flush()

    clips: list[Clip] = []
    for rank, cand in enumerate(top, start=1):
        clip = Clip(
            video_id=video.id,
            rank=rank,
            start_time=cand.start,
            end_time=cand.end,
            duration=round(cand.end - cand.start, 2),
            score=cand.score,
            reasons=cand.reasons,
            signals=cand.signals,
            title=f"Clip {rank:02d} — {format_range(cand.start, cand.end)}",
            status="ready",
        )
        db.add(clip)
        db.flush()
        try:
            thumb = settings.data_dir / "thumbnails" / f"clip_{clip.id}.jpg"
            ffmpeg_service.extract_thumbnail(video_path, thumb, (cand.start + cand.end) / 2)
            clip.thumbnail_path = str(thumb)
        except Exception as exc:  # noqa: BLE001 - thumbnails are best-effort
            logger.warning("clip thumbnail failed: %s", exc)
        clips.append(clip)

    video.status = "completed"
    video.progress = 100.0
    video.stage_message = f"Found {len(clips)} clips"
    video.analysis_options = {"clip_duration": clip_duration, "num_clips": num_clips}
    db.commit()

    log_event(logger, "analysis_completed", video_id=video_id, clips=len(clips))
    report(100, "completed", f"Found {len(clips)} clips")
    return clips
