"""Audio engagement analysis from an extracted mono WAV track.

Computes per-window RMS / peak / energy (normalized), an energy-based speech
activity estimate, silence masks, loud moments (sudden energy jumps) and
silence breaks (speech → silence → speech). Pure stdlib + numpy: no heavy
audio ML dependency required.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from ..config import get_settings
from ..utils.logging import get_logger
from . import ffmpeg_service
from .interfaces import AudioFeatures

logger = get_logger(__name__)


class EnergyAudioAnalyzer:
    name = "energy_audio_analyzer"

    def __init__(self, window: float | None = None, sample_rate: int | None = None):
        settings = get_settings()
        self.window = window or settings.audio_window_seconds
        self.sample_rate = sample_rate or settings.audio_sample_rate

    def analyze(self, video_path: str, duration: float) -> AudioFeatures:
        settings = get_settings()
        tmp_wav = Path(settings.data_dir) / "temp" / f"audio_{Path(video_path).stem}.wav"
        try:
            ffmpeg_service.extract_audio_wav(video_path, tmp_wav, self.sample_rate)
            samples = self._read_wav_mono(tmp_wav)
        except RuntimeError as exc:
            logger.warning("audio analysis skipped (no audio?): %s", exc)
            return self._empty(duration)
        finally:
            if settings.cleanup_temp_files:
                tmp_wav.unlink(missing_ok=True)

        if samples.size == 0:
            return self._empty(duration)

        per_window = int(self.sample_rate * self.window)
        n_windows = max(1, int(len(samples) / per_window))
        usable = n_windows * per_window
        frames = samples[:usable].reshape(n_windows, per_window)

        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        peak = np.max(np.abs(frames), axis=1).astype(np.float64)
        # Normalize against robust maxima so one spike doesn't flatten everything.
        rms_norm = self._robust_norm(rms)
        peak_norm = self._robust_norm(peak)
        energy = np.clip(0.6 * rms_norm + 0.4 * peak_norm, 0.0, 1.0)

        # Speech activity: sustained mid-energy with variability (cheap VAD).
        noise_floor = float(np.percentile(rms_norm, 15))
        speech = np.clip((rms_norm - noise_floor) / max(1e-6, 0.6 - noise_floor), 0.0, 1.0)
        variability = np.abs(np.diff(rms_norm, prepend=rms_norm[0]))
        speech = np.clip(speech * (0.5 + 0.5 * np.clip(variability * 4.0, 0, 1)), 0, 1)

        silence = rms_norm < max(0.03, noise_floor * 0.6)
        times = [round(i * self.window, 3) for i in range(n_windows)]

        loud_moments = self._detect_loud_moments(times, energy)
        silence_breaks = self._detect_silence_breaks(times, speech, silence)

        logger.info(
            "audio analyzed: %d windows, %d loud moments, %d silence breaks",
            n_windows,
            len(loud_moments),
            len(silence_breaks),
        )
        return AudioFeatures(
            times=times,
            rms=[round(float(v), 4) for v in rms_norm],
            peak=[round(float(v), 4) for v in peak_norm],
            energy=[round(float(v), 4) for v in energy],
            speech=[round(float(v), 4) for v in speech],
            silence=[bool(v) for v in silence],
            loud_moments=loud_moments,
            silence_breaks=silence_breaks,
            window=self.window,
        )

    def _empty(self, duration: float) -> AudioFeatures:
        n = max(1, int(duration / self.window))
        return AudioFeatures(
            times=[round(i * self.window, 3) for i in range(n)],
            rms=[0.0] * n,
            peak=[0.0] * n,
            energy=[0.0] * n,
            speech=[0.0] * n,
            silence=[True] * n,
            loud_moments=[],
            silence_breaks=[],
            window=self.window,
        )

    @staticmethod
    def _read_wav_mono(path: Path) -> np.ndarray:
        with wave.open(str(path), "rb") as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            sampwidth = wf.getsampwidth()
            nch = wf.getnchannels()
        if sampwidth == 1:
            data = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
            data /= 128.0
        elif sampwidth == 2:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        else:
            data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
        if nch > 1:
            data = data.reshape(-1, nch).mean(axis=1)
        return data

    @staticmethod
    def _robust_norm(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        ceiling = float(np.percentile(values, 99.0))
        if ceiling <= 1e-9:
            return np.zeros_like(values)
        return np.clip(values / ceiling, 0.0, 1.0)

    def _detect_loud_moments(self, times: list[float], energy: np.ndarray) -> list[float]:
        if energy.size < 4:
            return []
        # Sudden jumps: current window well above trailing median + absolute floor.
        moments: list[float] = []
        kernel = 8
        for i in range(kernel, len(energy)):
            baseline = float(np.median(energy[max(0, i - kernel) : i]))
            if energy[i] >= 0.55 and energy[i] - baseline >= 0.25:
                # Debounce: keep local maxima at least ~2s apart.
                if not moments or times[i] - moments[-1] > 2.0:
                    moments.append(round(times[i], 2))
        return moments

    def _detect_silence_breaks(
        self, times: list[float], speech: np.ndarray, silence: np.ndarray
    ) -> list[float]:
        breaks: list[float] = []
        n = len(times)
        i = 0
        while i < n:
            if silence[i]:
                j = i
                while j < n and silence[j]:
                    j += 1
                gap_len = (j - i) * self.window
                speech_before = float(np.mean(speech[max(0, i - 6) : i])) if i > 0 else 0.0
                speech_after = float(np.mean(speech[j : j + 6])) if j < n else 0.0
                # speech → silence(0.4–4s) → speech, or silence → strong re-entry
                if 0.4 <= gap_len <= 4.0 and (speech_before > 0.25 or speech_after > 0.35):
                    breaks.append(round(times[min(j, n - 1)], 2))
                i = j
            else:
                i += 1
        return breaks
