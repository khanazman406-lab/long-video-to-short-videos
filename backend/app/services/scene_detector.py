"""Scene / cut detection via sampled-frame differencing.

Samples frames at SCENE_SAMPLE_FPS, downscaled for speed, and scores each
frame against its predecessor using HSV-histogram correlation plus mean
absolute difference. Large discontinuities become SceneEvents; dense clusters
of events double as the fast-cut signal. Preferring clip boundaries near
these events keeps cuts on natural transitions.
"""

from __future__ import annotations

import cv2  # type: ignore
import numpy as np

from ..config import get_settings
from ..utils.logging import get_logger
from .interfaces import SceneEvent

logger = get_logger(__name__)


class HistogramSceneDetector:
    name = "histogram_scene_detector"

    def __init__(
        self,
        sample_fps: float | None = None,
        frame_width: int | None = None,
        threshold: float = 0.45,
    ):
        settings = get_settings()
        self.sample_fps = sample_fps or settings.scene_sample_fps
        self.frame_width = frame_width or settings.analysis_frame_width
        self.threshold = threshold

    def detect(self, video_path: str, duration: float) -> list[SceneEvent]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("scene detector: cannot open %s", video_path)
            return []
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        stride = max(1, int(round(src_fps / self.sample_fps)))

        events: list[SceneEvent] = []
        prev_hist = None
        prev_gray = None
        diffs: list[float] = []
        frame_idx = 0
        sampled = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if frame_idx % stride != 0:
                frame_idx += 1
                continue
            ok, frame = cap.retrieve()
            frame_idx += 1
            if not ok or frame is None:
                continue
            small = self._downscale(frame)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            t = frame_idx / src_fps if src_fps else sampled / self.sample_fps
            if prev_hist is not None and prev_gray is not None:
                corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                hist_diff = float(np.clip(1.0 - corr, 0.0, 1.0))
                abs_diff = float(np.mean(cv2.absdiff(prev_gray, gray)) / 255.0)
                score = 0.65 * hist_diff + 0.35 * abs_diff
                diffs.append(score)
                if score >= self.threshold and t > 0.5 and t < max(0.0, duration - 0.5):
                    events.append(SceneEvent(time=t, strength=float(min(1.0, score))))
            prev_hist, prev_gray = hist, gray
            sampled += 1

        cap.release()
        # Adaptive fallback: if nothing passed the fixed threshold, take top outliers.
        if not events and len(diffs) > 10:
            arr = np.array(diffs)
            cutoff = float(np.mean(arr) + 2.0 * np.std(arr))
            # re-walk is expensive; approximate event times from stride positions
            for i, d in enumerate(diffs):
                if d >= max(cutoff, 0.25):
                    events.append(SceneEvent(time=(i + 1) * stride / src_fps, strength=float(min(1.0, d))))
        events.sort(key=lambda e: e.time)
        logger.info("scene detector: %d events in %s", len(events), video_path)
        return events

    def _downscale(self, frame):
        h, w = frame.shape[:2]
        if w <= self.frame_width:
            return frame
        scale = self.frame_width / float(w)
        return cv2.resize(frame, (self.frame_width, max(1, int(h * scale))))
