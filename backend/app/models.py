"""SQLAlchemy models: Video, Clip, Export."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(128), default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    video_codec: Mapped[str] = mapped_column(String(64), default="")
    audio_codec: Mapped[str] = mapped_column(String(64), default="")
    # queued|uploading|extracting|analyzing|scoring|generating_clips|exporting|completed|failed
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage_message: Mapped[str] = mapped_column(String(512), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    video_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    thumbnail_path: Mapped[str] = mapped_column(Text, default="")
    analysis_options: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clips: Mapped[list["Clip"]] = relationship(
        "Clip", back_populates="video", cascade="all, delete-orphan", order_by="Clip.rank"
    )


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    start_time: Mapped[float] = mapped_column(Float, default=0.0)
    end_time: Mapped[float] = mapped_column(Float, default=0.0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    title: Mapped[str] = mapped_column(String(256), default="")
    thumbnail_path: Mapped[str] = mapped_column(Text, default="")
    # ready|exporting|exported|failed
    status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    video: Mapped[Video] = relationship("Video", back_populates="clips")
    exports: Mapped[list["Export"]] = relationship(
        "Export", back_populates="clip", cascade="all, delete-orphan"
    )


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(String(32), ForeignKey("clips.id"), index=True)
    video_id: Mapped[str] = mapped_column(String(32), index=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    output_format: Mapped[str] = mapped_column(String(16), default="mp4")
    quality: Mapped[str] = mapped_column(String(16), default="balanced")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    # queued|exporting|completed|failed
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    output_path: Mapped[str] = mapped_column(Text, default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clip: Mapped[Clip] = relationship("Clip", back_populates="exports")
