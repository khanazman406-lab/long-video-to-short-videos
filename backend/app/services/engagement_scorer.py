"""Transparent engagement scoring over fixed time windows.

Engagement Score =
    Audio Energy      x w1
  + Speech Activity   x w2
  + Scene Changes     x w3
  + Motion Intensity  x w4
  + Face Activity     x w5
  + Silence Break     x w6
  + Visual Change     x w7
  + Transcript Signal x w8

Weights come from Settings (SCORING_WEIGHTS env). Every window also gets
human-readable reasons so the UI can show *why* a clip scored highly. This
is an engagement heuristic — it never claims to predict actual virality.
"""

from __future__ import annotations

import math

import numpy as np

from ..config import get_settings
from .interfaces import (
    AudioFeatures,
    FaceObservation,
    MotionFeatures,
    SceneEvent,
    TranscriptSegment,
)

REASON_LABELS = {
    "audio_energy": "High audio energy",
    "speech_activity": "Active speech",
    "scene_changes": "Strong scene transition",
    "motion_intensity": "High motion / action",
    "face_activity": "Face detected",
    "silence_break": "Natural speech break",
    "visual_change": "Strong visual change",
    "transcript_signal": "Hook-worthy speech",
}

# A signal must reach this level to earn a "reason" badge.
REASON_THRESHOLDS = {
    "audio_energy": 0.55,
    "speech_activity": 0.55,
    "scene_changes": 0.35,
    "motion_intensity": 0.55,
    "face_activity": 0.35,
    "silence_break": 0.5,
    "visual_change": 0.5,
    "transcript_signal": 0.4,
}


class WeightedEngagementScorer:
    name = "weighted_engagement_scorer"

    def __init__(self, weights: dict[str, float] | None = None, window: float = 1.0):
        self.weights = weights or get_settings().scoring_weights()
        self.window = window

    def score_windows(
        self,
        duration: float,
        window: float,
        audio: AudioFeatures,
        scenes: list[SceneEvent],
        faces: list[FaceObservation],
        motion: MotionFeatures,
        transcripts: list[TranscriptSegment],
    ) -> list[dict]:
        self.window = window
        n = max(1, int(math.ceil(duration / window)))
        scene_density = self._density_from_events([s.time for s in scenes], [s.strength for s in scenes], duration, n)
        cut_counts = self._counts_from_events([s.time for s in scenes], duration, n)
        face_signal, face_density = self._face_signals(faces, duration, n)
        transcript_signal = self._transcript_signal(transcripts, duration, n)
        silence_break_signal = self._event_proximity(audio.silence_breaks, duration, n, radius=1.5)
        loud_signal = self._event_proximity(audio.loud_moments, duration, n, radius=1.0)

        audio_energy = self._resample(audio.times, audio.energy, duration, n)
        speech = self._resample(audio.times, audio.speech, duration, n)
        motion_sig = self._resample(motion.times, motion.intensity, duration, n)

        # Fast cuts: normalize cut counts into 0..1 and blend with scene strength.
        max_cuts = max(cut_counts) if cut_counts else 0
        scene_changes = [
            float(min(1.0, 0.7 * scene_density[i] + (0.3 * cut_counts[i] / max_cuts if max_cuts else 0.0)))
            for i in range(n)
        ]
        # Visual change blends scene strength with motion for gradual transitions.
        visual_change = [float(min(1.0, 0.5 * scene_density[i] + 0.5 * motion_sig[i])) for i in range(n)]
        # Audio energy gets a loud-moment bonus (reactions, laughter, drops).
        audio_boosted = [float(min(1.0, audio_energy[i] * 0.8 + loud_signal[i] * 0.4)) for i in range(n)]

        signals = {
            "audio_energy": audio_boosted,
            "speech_activity": speech,
            "scene_changes": scene_changes,
            "motion_intensity": motion_sig,
            "face_activity": face_signal,
            "silence_break": silence_break_signal,
            "visual_change": visual_change,
            "transcript_signal": transcript_signal,
        }

        results: list[dict] = []
        for i in range(n):
            total = sum(signals[k][i] * self.weights.get(k, 0.0) for k in signals)
            score = round(float(total) * 100.0, 1)
            reasons = [
                REASON_LABELS[k]
                for k in signals
                if signals[k][i] >= REASON_THRESHOLDS.get(k, 0.6)
            ]
            results.append(
                {
                    "index": i,
                    "start": round(i * window, 2),
                    "end": round(min(duration, (i + 1) * window), 2),
                    "score": score,
                    "reasons": reasons[:6],
                    "signals": {k: round(float(signals[k][i]), 3) for k in signals},
                    "face_count": face_density[i],
                }
            )
        return results

    # -- helpers ---------------------------------------------------------
    def _resample(self, times: list[float], values: list[float], duration: float, n: int) -> list[float]:
        if not times or not values:
            return [0.0] * n
        arr_t = np.array(times)
        arr_v = np.array(values, dtype=float)
        out: list[float] = []
        for i in range(n):
            lo, hi = i * self.window, (i + 1) * self.window
            mask = (arr_t >= lo) & (arr_t < hi)
            out.append(float(np.mean(arr_v[mask])) if np.any(mask) else 0.0)
        # Smooth with a small moving average to avoid single-window spikes.
        kernel = 3
        smoothed = []
        for i in range(n):
            lo = max(0, i - 1)
            hi = min(n, i + 2)
            smoothed.append(sum(out[lo:hi]) / max(1, hi - lo))
        return smoothed

    def _density_from_events(
        self, times: list[float], strengths: list[float], duration: float, n: int
    ) -> list[float]:
        density = [0.0] * n
        for t, s in zip(times, strengths):
            idx = min(n - 1, max(0, int(t / self.window)))
            density[idx] = min(1.0, density[idx] + 0.6 * float(s) + 0.4)
            # Spread to neighbors so boundaries near cuts still score.
            for j in (idx - 1, idx + 1):
                if 0 <= j < n:
                    density[j] = min(1.0, density[j] + 0.25 * float(s))
        return density

    def _counts_from_events(self, times: list[float], duration: float, n: int) -> list[int]:
        counts = [0] * n
        for t in times:
            counts[min(n - 1, max(0, int(t / self.window)))] += 1
        return counts

    def _event_proximity(self, times: list[float], duration: float, n: int, radius: float) -> list[float]:
        if not times:
            return [0.0] * n
        arr = np.array(sorted(times))
        out = []
        for i in range(n):
            center = (i + 0.5) * self.window
            dist = float(np.min(np.abs(arr - center)))
            out.append(float(max(0.0, 1.0 - dist / radius)) if dist <= radius else 0.0)
        return out

    def _face_signals(self, faces: list[FaceObservation], duration: float, n: int) -> tuple[list[float], list[int]]:
        presence = [0.0] * n
        counts = [0] * n
        prev_count = 0
        for obs in faces:
            idx = min(n - 1, max(0, int(obs.time / self.window)))
            presence[idx] = min(1.0, presence[idx] + 0.5 + 0.25 * min(obs.count, 3))
            counts[idx] = max(counts[idx], obs.count)
            # Appearance/disappearance transitions earn a bonus.
            if obs.count != prev_count:
                presence[idx] = min(1.0, presence[idx] + 0.25)
            prev_count = obs.count
        return presence, counts

    def _transcript_signal(self, transcripts: list[TranscriptSegment], duration: float, n: int) -> list[float]:
        signal = [0.0] * n
        for seg in transcripts:
            if seg.score <= 0:
                continue
            lo = max(0, int(seg.start / self.window))
            hi = min(n - 1, int(seg.end / self.window))
            for i in range(lo, hi + 1):
                signal[i] = max(signal[i], float(seg.score))
        return signal
