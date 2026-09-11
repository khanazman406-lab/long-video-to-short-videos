"""Speech-to-text integration point with hook-phrase scoring.

Uses faster-whisper when installed (server-side, local model) and degrades
gracefully to a null analyzer otherwise — transcript scoring is optional and
never blocks the pipeline. Hook phrases (questions, strong claims, reactions)
earn a transcript_signal bonus in engagement scoring.
"""

from __future__ import annotations

import re

from ..config import get_settings
from ..utils.logging import get_logger
from .interfaces import TranscriptSegment

logger = get_logger(__name__)

HOOK_PATTERNS = [
    re.compile(r"\?"),  # questions
    re.compile(r"\b(never|always|everyone|nobody|secret|mistake|truth|free|best|worst|amazing|insane|crazy|huge)\b", re.I),
    re.compile(r"\b(i swear|oh my|wow|wait|look at|listen|here'?s the thing|the most important)\b", re.I),
    re.compile(r"!"),
    re.compile(r"\b(don'?t|stop|never do|you need to|you should|remember)\b", re.I),
]


def score_hook_value(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    hits = sum(1 for rx in HOOK_PATTERNS if rx.search(text))
    length_bonus = 0.1 if 20 <= len(text) <= 220 else 0.0
    return round(min(1.0, hits * 0.25 + length_bonus), 3)


class NullTranscriptAnalyzer:
    """Fallback when no STT engine is available."""

    name = "null_transcript"
    available = False

    def transcribe(self, video_path: str, duration: float) -> list[TranscriptSegment]:
        return []


class WhisperTranscriptAnalyzer:
    """Local faster-whisper transcription (optional dependency)."""

    name = "faster_whisper"
    available = True

    def __init__(self, model_size: str | None = None):
        settings = get_settings()
        self.model_size = model_size or settings.transcript_model
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, video_path: str, duration: float) -> list[TranscriptSegment]:
        try:
            model = self._load()
        except Exception as exc:  # noqa: BLE001 - optional engine
            logger.warning("whisper unavailable, skipping transcripts: %s", exc)
            return []
        try:
            segments, _ = model.transcribe(video_path, beam_size=3, vad_filter=True)
            out: list[TranscriptSegment] = []
            for seg in segments:
                text = (seg.text or "").strip()
                if not text:
                    continue
                out.append(
                    TranscriptSegment(
                        start=round(float(seg.start), 2),
                        end=round(float(seg.end), 2),
                        text=text,
                        score=score_hook_value(text),
                    )
                )
            logger.info("transcribed %d segments", len(out))
            return out
        except Exception as exc:  # noqa: BLE001 - transcription must not break analysis
            logger.warning("transcription failed: %s", exc)
            return []


def get_transcript_analyzer():
    settings = get_settings()
    if not settings.transcript_enabled:
        return NullTranscriptAnalyzer()
    try:
        import faster_whisper  # noqa: F401  # type: ignore
    except ImportError:
        return NullTranscriptAnalyzer()
    return WhisperTranscriptAnalyzer()
