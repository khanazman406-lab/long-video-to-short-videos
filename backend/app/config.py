"""ClipForge AI — centralized application configuration.

Every tunable value (limits, scoring weights, presets, retention) lives here
and can be overridden with environment variables so an administrator never
needs to hunt through source code. See .env.example at the repo root.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve repo-relative defaults: backend/app/config.py -> backend/ -> repo root
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Branding (rename the app by changing these + frontend/src/lib/brand.ts) ---
    app_name: str = Field(default="ClipForge AI", alias="APP_NAME")
    app_tagline: str = Field(
        default="Turn long videos into your best short clips automatically.",
        alias="APP_TAGLINE",
    )

    # --- Server ---
    api_prefix: str = "/api"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # --- Database (SQLite default, PostgreSQL for production) ---
    database_url: str = Field(
        default=f"sqlite:///{BACKEND_DIR / 'data' / 'clipforge.db'}",
        alias="DATABASE_URL",
    )

    # --- Queue (optional Redis/RQ; falls back to in-process worker pool) ---
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    use_redis_queue: bool = Field(default=False, alias="USE_REDIS_QUEUE")
    worker_concurrency: int = Field(default=2, alias="WORKER_CONCURRENCY")

    # --- Storage abstraction ---
    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")  # local | s3
    storage_bucket: str = Field(default="", alias="STORAGE_BUCKET")
    storage_access_key: str = Field(default="", alias="STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(default="", alias="STORAGE_SECRET_KEY")
    storage_region: str = Field(default="us-east-1", alias="STORAGE_REGION")
    storage_endpoint: str = Field(default="", alias="STORAGE_ENDPOINT")
    data_dir: Path = Field(default=BACKEND_DIR / "data", alias="DATA_DIR")

    # --- Upload limits / validation ---
    max_upload_size: int = Field(default=2 * 1024 * 1024 * 1024, alias="MAX_UPLOAD_SIZE")  # 2 GB
    max_video_duration: float = Field(default=3 * 3600.0, alias="MAX_VIDEO_DURATION")  # 3 h
    min_video_duration: float = Field(default=5.0, alias="MIN_VIDEO_DURATION")
    allowed_extensions: str = Field(default="mp4,mov,webm,mkv,m4v", alias="ALLOWED_EXTENSIONS")
    allowed_mime_types: str = Field(
        default="video/mp4,video/quicktime,video/webm,video/x-matroska,video/x-m4v",
        alias="ALLOWED_MIME_TYPES",
    )

    # --- FFmpeg ---
    ffmpeg_path: str = Field(default="", alias="FFMPEG_PATH")  # auto-detected if empty
    ffmpeg_threads: int = Field(default=0, alias="FFMPEG_THREADS")  # 0 = auto

    # --- Analysis ---
    analysis_frame_width: int = Field(default=320, alias="ANALYSIS_FRAME_WIDTH")
    scene_sample_fps: float = Field(default=2.0, alias="SCENE_SAMPLE_FPS")
    face_sample_fps: float = Field(default=1.0, alias="FACE_SAMPLE_FPS")
    audio_window_seconds: float = Field(default=0.5, alias="AUDIO_WINDOW_SECONDS")
    audio_sample_rate: int = Field(default=16000, alias="AUDIO_SAMPLE_RATE")
    transcript_enabled: bool = Field(default=True, alias="TRANSCRIPT_ENABLED")
    transcript_model: str = Field(default="tiny", alias="TRANSCRIPT_MODEL")  # faster-whisper size

    # --- Clip generation ---
    default_num_clips: int = Field(default=10, alias="DEFAULT_NUM_CLIPS")
    max_num_clips: int = Field(default=20, alias="MAX_NUM_CLIPS")
    default_clip_duration: float = Field(default=30.0, alias="DEFAULT_CLIP_DURATION")
    min_clip_duration: float = Field(default=5.0, alias="MIN_CLIP_DURATION")
    max_clip_duration: float = Field(default=180.0, alias="MAX_CLIP_DURATION")
    event_merge_gap: float = Field(default=6.0, alias="EVENT_MERGE_GAP")
    overlap_threshold: float = Field(default=0.5, alias="OVERLAP_THRESHOLD")

    # --- Engagement scoring weights (must sum ~ 1.0) ---
    scoring_weights_json: str = Field(
        default=json.dumps(
            {
                "audio_energy": 0.20,
                "speech_activity": 0.15,
                "scene_changes": 0.15,
                "motion_intensity": 0.15,
                "face_activity": 0.10,
                "silence_break": 0.10,
                "visual_change": 0.10,
                "transcript_signal": 0.05,
            }
        ),
        alias="SCORING_WEIGHTS",
    )

    # --- Retention / privacy ---
    cleanup_temp_files: bool = Field(default=True, alias="CLEANUP_TEMP_FILES")
    retention_days: int = Field(default=30, alias="RETENTION_DAYS")

    # --- Rate limiting (requests per minute per IP) ---
    rate_limit_per_minute: int = Field(default=120, alias="RATE_LIMIT_PER_MINUTE")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _join_list(cls, v):  # allow JSON list or comma string
        if isinstance(v, list):
            return ",".join(v)
        return v

    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def allowed_extension_list(self) -> list[str]:
        return [e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()]

    def allowed_mime_list(self) -> list[str]:
        return [m.strip().lower() for m in self.allowed_mime_types.split(",") if m.strip()]

    def scoring_weights(self) -> dict[str, float]:
        try:
            weights = json.loads(self.scoring_weights_json)
            total = sum(weights.values()) or 1.0
            return {k: float(v) / total for k, v in weights.items()}
        except (ValueError, AttributeError, TypeError):
            return {
                "audio_energy": 0.20,
                "speech_activity": 0.15,
                "scene_changes": 0.15,
                "motion_intensity": 0.15,
                "face_activity": 0.10,
                "silence_break": 0.10,
                "visual_change": 0.10,
                "transcript_signal": 0.05,
            }

    def ensure_data_dirs(self) -> None:
        for sub in ("uploads", "thumbnails", "exports", "temp", "waveforms"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # DATA_DIR may come from env as str; pydantic coerces to Path
    settings.ensure_data_dirs()
    return settings


def get_data_dir() -> Path:
    return Path(get_settings().data_dir)
