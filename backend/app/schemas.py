"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    ffmpeg: bool
    database: bool
    queue: bool
    transcript_engine: str


class VideoResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    status: str
    progress: float
    stage_message: str
    error_message: str = ""
    thumbnail_url: str = ""
    num_clips: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class VideoStatusResponse(BaseModel):
    id: str
    status: str
    progress: float
    stage_message: str
    error_message: str = ""
    num_clips: int = 0


class AnalyzeRequest(BaseModel):
    clip_duration: float = Field(default=30.0, ge=5.0, le=180.0)
    num_clips: int = Field(default=10, ge=1, le=20)


class AnalyzeResponse(BaseModel):
    video_id: str
    job_id: str
    status: str
    message: str


class ClipResponse(BaseModel):
    id: str
    video_id: str
    rank: int
    start_time: float
    end_time: float
    duration: float
    score: float
    reasons: list[str] = []
    signals: dict = {}
    title: str = ""
    thumbnail_url: str = ""
    status: str

    model_config = {"from_attributes": True}


class ClipListResponse(BaseModel):
    video_id: str
    count: int
    clips: list[ClipResponse]


class ClipUpdateRequest(BaseModel):
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, ge=0)
    title: str | None = None


class ExportRequest(BaseModel):
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")
    output_format: str = Field(default="mp4", pattern="^(mp4|webm)$")
    quality: str = Field(default="balanced", pattern="^(fast|balanced|high)$")


class ExportAllRequest(BaseModel):
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")
    output_format: str = Field(default="mp4", pattern="^(mp4|webm)$")
    quality: str = Field(default="balanced", pattern="^(fast|balanced|high)$")
    clip_ids: list[str] | None = None


class ExportResponse(BaseModel):
    id: str
    clip_id: str
    video_id: str
    aspect_ratio: str
    output_format: str
    quality: str
    width: int
    height: int
    status: str
    progress: float
    file_size: int
    error_message: str = ""
    download_url: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExportListResponse(BaseModel):
    video_id: str
    count: int
    exports: list[ExportResponse]


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
