"""Analyzer interfaces — every detector implements one of these.

This keeps the pipeline modular: swap Haar faces for a DNN model, or the
energy-based speech detector for Whisper, without touching the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SceneEvent:
    time: float
    strength: float  # 0..1 magnitude of the visual change


@dataclass
class AudioFeatures:
    """Per-window audio features sampled every `window` seconds."""

    times: list[float] = field(default_factory=list)
    rms: list[float] = field(default_factory=list)  # normalized 0..1
    peak: list[float] = field(default_factory=list)  # normalized 0..1
    energy: list[float] = field(default_factory=list)  # normalized 0..1
    speech: list[float] = field(default_factory=list)  # 0..1 speech activity
    silence: list[bool] = field(default_factory=list)
    loud_moments: list[float] = field(default_factory=list)  # timestamps
    silence_breaks: list[float] = field(default_factory=list)  # timestamps
    window: float = 0.5


@dataclass
class MotionFeatures:
    times: list[float] = field(default_factory=list)
    intensity: list[float] = field(default_factory=list)  # normalized 0..1
    window: float = 0.5


@dataclass
class FaceObservation:
    time: float
    count: int
    boxes: list[tuple[int, int, int, int]]  # x, y, w, h in analysis resolution
    frame_width: int
    frame_height: int


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    score: float = 0.0  # hook-value score 0..1


class SceneAnalyzer(Protocol):
    name: str

    def detect(self, video_path: str, duration: float) -> list[SceneEvent]: ...


class AudioAnalyzer(Protocol):
    name: str

    def analyze(self, video_path: str, duration: float) -> AudioFeatures: ...


class FaceAnalyzer(Protocol):
    name: str

    def detect(self, video_path: str, duration: float) -> list[FaceObservation]: ...


class MotionAnalyzer(Protocol):
    name: str

    def analyze(self, video_path: str, duration: float) -> MotionFeatures: ...


class TranscriptAnalyzer(Protocol):
    name: str
    available: bool

    def transcribe(self, video_path: str, duration: float) -> list[TranscriptSegment]: ...


class EngagementScorer(Protocol):
    def score_windows(
        self,
        duration: float,
        window: float,
        audio: AudioFeatures,
        scenes: list[SceneEvent],
        faces: list[FaceObservation],
        motion: MotionFeatures,
        transcripts: list[TranscriptSegment],
    ) -> list[dict]: ...
