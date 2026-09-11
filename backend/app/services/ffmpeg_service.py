"""FFmpeg integration — probing, audio extraction, thumbnails, exports.

Resolves the ffmpeg binary from (in order): FFMPEG_PATH env, system PATH,
imageio-ffmpeg's bundled binary. All invocations use argv lists (never shell)
so user filenames can never become shell commands. Metadata is read via
`ffmpeg -i` stderr parsing plus an OpenCV fallback, so no ffprobe needed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings
from ..utils.logging import get_logger
from ..utils.security import ValidationError

logger = get_logger(__name__)

_FFMPEG_EXE: str | None = None


def get_ffmpeg_exe() -> str:
    global _FFMPEG_EXE
    if _FFMPEG_EXE:
        return _FFMPEG_EXE
    settings = get_settings()
    candidates: list[str] = []
    if settings.ffmpeg_path:
        candidates.append(settings.ffmpeg_path)
    system = shutil.which("ffmpeg")
    if system:
        candidates.append(system)
    try:
        import imageio_ffmpeg  # type: ignore

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # pragma: no cover - optional dependency path
        pass
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            _FFMPEG_EXE = candidate
            return candidate
    raise RuntimeError(
        "No FFmpeg binary found. Install system ffmpeg or `pip install imageio-ffmpeg`."
    )


def ffmpeg_available() -> bool:
    try:
        get_ffmpeg_exe()
        return True
    except RuntimeError:
        return False


def run_ffmpeg(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run ffmpeg with an argv list. Raises ValidationError-safe RuntimeError."""
    exe = get_ffmpeg_exe()
    cmd = [exe, "-hide_banner", "-nostdin", "-y", *args]
    logger.info("ffmpeg run: %s", " ".join(cmd[:4]) + " ...")
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg timed out: {exc}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg binary not found.") from exc


@dataclass
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    has_video: bool
    has_audio: bool
    raw: dict


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")
_VIDEO_RE = re.compile(r"Stream.*Video:\s*([a-zA-Z0-9_]+)[^,]*,\s*[^,]*,\s*(\d+)x(\d+)[^,]*,\s*([\d.]+)\s*fps")
_VIDEO_RE_LOOSE = re.compile(r"Stream.*Video:\s*([a-zA-Z0-9_]+)")
_RES_RE = re.compile(r"(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"([\d.]+)\s*fps")
_AUDIO_RE = re.compile(r"Stream.*Audio:\s*([a-zA-Z0-9_]+)")


def probe_video(path: str | Path) -> VideoMetadata:
    """Extract metadata. Raises ValidationError for unreadable/corrupt files."""
    exe = get_ffmpeg_exe()
    proc = subprocess.run(
        [exe, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    stderr = proc.stderr or ""
    if "Invalid data found" in stderr and "Duration" not in stderr:
        raise ValidationError("Video could not be decoded. The file may be corrupted.")

    duration = 0.0
    m = _DURATION_RE.search(stderr)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    width = height = 0
    fps = 0.0
    video_codec = ""
    mv = _VIDEO_RE.search(stderr)
    if mv:
        video_codec = mv.group(1)
        width, height = int(mv.group(2)), int(mv.group(3))
        fps = float(mv.group(4))
    else:
        ml = _VIDEO_RE_LOOSE.search(stderr)
        if ml:
            video_codec = ml.group(1)
            mr = _RES_RE.search(stderr)
            if mr:
                width, height = int(mr.group(1)), int(mr.group(2))
            mf = _FPS_RE.search(stderr)
            if mf:
                try:
                    fps = float(mf.group(1))
                except ValueError:
                    fps = 0.0

    audio_codec = ""
    ma = _AUDIO_RE.search(stderr)
    if ma:
        audio_codec = ma.group(1)

    has_video = "Video:" in stderr
    has_audio = "Audio:" in stderr
    if not has_video:
        # OpenCV fallback before giving up (some containers confuse the regex)
        try:
            import cv2  # type: ignore

            cap = cv2.VideoCapture(str(path))
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                width, height = width or w, height or h
                has_video = True
        except Exception:
            pass
    if not has_video:
        raise ValidationError("Video contains no usable video stream.")

    if duration <= 0:
        # Fallback: derive duration via OpenCV frame count
        try:
            import cv2  # type: ignore

            cap = cv2.VideoCapture(str(path))
            count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            vf = cap.get(cv2.CAP_PROP_FPS) or 0
            cap.release()
            if count and vf:
                duration = count / vf
        except Exception:
            pass

    return VideoMetadata(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        video_codec=video_codec,
        audio_codec=audio_codec,
        has_video=has_video,
        has_audio=has_audio,
        raw={"probe": stderr[-2000:]},
    )


def extract_audio_wav(video_path: str | Path, out_wav: str | Path, sample_rate: int = 16000) -> Path:
    """Extract mono PCM audio for analysis. Raises RuntimeError on failure."""
    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            str(out),
        ],
        timeout=900,
    )
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"Audio extraction failed: {(proc.stderr or '')[-500:]}")
    return out


def extract_thumbnail(video_path: str | Path, out_jpg: str | Path, at_seconds: float, width: int = 480) -> Path:
    out = Path(out_jpg)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = run_ffmpeg(
        [
            "-ss",
            f"{max(0.0, at_seconds):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-q:v",
            "4",
            str(out),
        ],
        timeout=120,
    )
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"Thumbnail extraction failed: {(proc.stderr or '')[-300:]}")
    return out


# Aspect-ratio targets: (width, height)
ASPECT_TARGETS = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (720, 720),
}

QUALITY_PRESETS = {
    "fast": {"preset": "veryfast", "crf": "28", "audio_bitrate": "96k"},
    "balanced": {"preset": "medium", "crf": "23", "audio_bitrate": "128k"},
    "high": {"preset": "slow", "crf": "18", "audio_bitrate": "192k"},
}


def build_crop_filter(
    src_w: int,
    src_h: int,
    aspect: str,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> tuple[str, int, int]:
    """Build a crop+scale filter chain for the target aspect ratio.

    focus_x/focus_y (0..1) pick the crop center so face-aware auto-reframe can
    keep the subject in frame for vertical/square outputs.
    """
    target_w, target_h = ASPECT_TARGETS.get(aspect, ASPECT_TARGETS["16:9"])
    target_ratio = target_w / target_h
    src_ratio = (src_w / src_h) if src_h else target_ratio

    fx = min(1.0, max(0.0, focus_x))
    fy = min(1.0, max(0.0, focus_y))

    if abs(src_ratio - target_ratio) < 0.01:
        vf = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,scale={target_w}:{target_h}"
        return vf, target_w, target_h

    if src_ratio > target_ratio:
        # Source is wider: crop width, keep full height.
        crop_h = src_h
        crop_w = int(src_h * target_ratio)
        x = int((src_w - crop_w) * fx)
        y = 0
    else:
        # Source is taller: crop height, keep full width.
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
        x = 0
        y = int((src_h - crop_h) * fy)

    crop_w = max(2, (crop_w // 2) * 2)
    crop_h = max(2, (crop_h // 2) * 2)
    x = max(0, min(src_w - crop_w, x))
    y = max(0, min(src_h - crop_h, y))
    vf = f"crop={crop_w}:{crop_h}:{x}:{y},scale={target_w}:{target_h}"
    return vf, target_w, target_h


def export_clip(
    video_path: str | Path,
    out_path: str | Path,
    start: float,
    end: float,
    aspect: str = "16:9",
    output_format: str = "mp4",
    quality: str = "balanced",
    src_w: int = 0,
    src_h: int = 0,
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> Path:
    """Render a clip segment to disk with aspect conversion. Returns output path."""
    if end <= start:
        raise ValidationError("Clip end must be after clip start.")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["balanced"])
    threads = get_settings().ffmpeg_threads

    probe_w, probe_h = src_w, src_h
    if not probe_w or not probe_h:
        try:
            meta = probe_video(video_path)
            probe_w, probe_h = meta.width or 1280, meta.height or 720
        except ValidationError:
            probe_w, probe_h = 1280, 720

    vf, _, _ = build_crop_filter(probe_w, probe_h, aspect, focus_x, focus_y)
    args: list[str] = [
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-i",
        str(video_path),
        "-vf",
        vf,
    ]
    if threads:
        args += ["-threads", str(threads)]
    if output_format == "webm":
        args += [
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            preset["crf"],
            "-c:a",
            "libopus",
            "-b:a",
            preset["audio_bitrate"],
        ]
    else:
        args += [
            "-c:v",
            "libx264",
            "-preset",
            preset["preset"],
            "-crf",
            preset["crf"],
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            preset["audio_bitrate"],
            "-movflags",
            "+faststart",
        ]
    args.append(str(out))
    proc = run_ffmpeg(args, timeout=1800)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"Export failed: {(proc.stderr or '')[-600:]}")
    return out
