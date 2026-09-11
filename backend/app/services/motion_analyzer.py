"""Motion intensity via downscaled frame differencing.

Cheap, resolution-independent signal for camera movement, action and gameplay
activity. Values are normalized across the whole video so long static
sections don't drown out the peaks.
"""

from __future__ import annotations

import cv2  # type: ignore
import numpy as np

from ..config import get_settings
from ..utils.logging import get_logger
from .interfaces import MotionFeatures

logger = get_logger(__name__)


class FrameDiffMotionAnalyzer:
    name = "frame_diff_motion"

    def __init__(self, sample_fps: float = 2.0, frame_width: int | None = None, window: float = 0.5):
        settings = get_settings()
        self.sample_fps = sample_fps
        self.frame_width = frame_width or min(256, settings.analysis_frame_width)
        self.window = window

    def analyze(self, video_path: str, duration: float) -> MotionFeatures:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return self._empty(duration)
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        stride = max(1, int(round(src_fps / self.sample_fps)))

        samples: list[tuple[float, float]] = []
        prev = None
        frame_idx = 0
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
            h, w = frame.shape[:2]
            scale = self.frame_width / float(w) if w > self.frame_width else 1.0
            small = cv2.resize(frame, (self.frame_width, max(1, int(h * scale)))) if scale < 1.0 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            t = frame_idx / src_fps if src_fps else 0.0
            if prev is not None:
                diff = cv2.absdiff(prev, gray)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                intensity = float(np.mean(thresh) / 255.0)
                samples.append((t, intensity))
            prev = gray
        cap.release()

        if not samples:
            return self._empty(duration)

        values = np.array([v for _, v in samples])
        ceiling = float(np.percentile(values, 99.0)) or 1.0
        normed = np.clip(values / ceiling, 0.0, 1.0)

        # Bin samples into fixed windows.
        n = max(1, int(duration / self.window) + 1)
        acc = np.zeros(n)
        counts = np.zeros(n)
        for (t, _), v in zip(samples, normed):
            idx = min(n - 1, int(t / self.window))
            acc[idx] += float(v)
            counts[idx] += 1
        intensity = [float(acc[i] / counts[i]) if counts[i] else 0.0 for i in range(n)]
        times = [round(i * self.window, 3) for i in range(n)]
        logger.info("motion analyzed: %d samples -> %d windows", len(samples), n)
        return MotionFeatures(times=times, intensity=intensity, window=self.window)

    def _empty(self, duration: float) -> MotionFeatures:
        n = max(1, int(duration / self.window) + 1)
        return MotionFeatures(
            times=[round(i * self.window, 3) for i in range(n)],
            intensity=[0.0] * n,
            window=self.window,
        )
