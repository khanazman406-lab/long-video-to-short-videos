"""Face detection with OpenCV's bundled Haar cascade.

Detects faces, counts, appearance/disappearance and position changes at
FACE_SAMPLE_FPS. The cascade ships with opencv-python-headless (no model
download needed). The class honors the FaceAnalyzer interface so a DNN /
emotion model can replace it later; low-confidence cascades are filtered via
minNeighbors/minSize so weak detections don't inflate scores.
"""

from __future__ import annotations

import cv2  # type: ignore

from ..config import get_settings
from ..utils.logging import get_logger
from .interfaces import FaceObservation

logger = get_logger(__name__)


class HaarFaceDetector:
    name = "haar_face_detector"

    def __init__(
        self,
        sample_fps: float | None = None,
        frame_width: int | None = None,
        min_neighbors: int = 6,
    ):
        settings = get_settings()
        self.sample_fps = sample_fps or settings.face_sample_fps
        self.frame_width = frame_width or settings.analysis_frame_width
        self.min_neighbors = min_neighbors
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            logger.warning("haar cascade failed to load from %s", cascade_path)
            self._cascade = None

    def detect(self, video_path: str, duration: float) -> list[FaceObservation]:
        if self._cascade is None:
            return []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        stride = max(1, int(round(src_fps / self.sample_fps)))

        observations: list[FaceObservation] = []
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
            if scale < 1.0:
                small = cv2.resize(frame, (self.frame_width, max(1, int(h * scale))))
            else:
                small = frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=self.min_neighbors,
                minSize=(24, 24),
            )
            t = frame_idx / src_fps if src_fps else 0.0
            boxes = [(int(x), int(y), int(bw), int(bh)) for (x, y, bw, bh) in faces]
            if boxes:
                observations.append(
                    FaceObservation(
                        time=round(t, 2),
                        count=len(boxes),
                        boxes=boxes,
                        frame_width=small.shape[1],
                        frame_height=small.shape[0],
                    )
                )
        cap.release()
        logger.info("face detector: %d observations in %s", len(observations), video_path)
        return observations

    def dominant_face_center(self, observations: list[FaceObservation], start: float, end: float) -> float | None:
        """Normalized x-center (0..1) of the largest face inside [start, end].

        Used by export auto-reframe to keep the subject in vertical crops.
        Returns None when no face is present in the window.
        """
        best = None
        best_area = 0
        for obs in observations:
            if not (start <= obs.time <= end):
                continue
            for (x, y, w, h) in obs.boxes:
                area = w * h
                if area > best_area:
                    best_area = area
                    best = (x + w / 2) / max(1, obs.frame_width)
        return best
