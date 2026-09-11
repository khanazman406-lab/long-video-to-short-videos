"""Upload validation unit tests."""

from __future__ import annotations

import pytest

from app.services.video_service import VideoValidator
from app.utils.security import ValidationError, sanitize_filename


def test_rejects_bad_extension(temp_env):
    with pytest.raises(ValidationError, match="Unsupported video format"):
        VideoValidator().validate_extension("movie.avi")


def test_accepts_supported_extensions(temp_env):
    for ext in ("mp4", "mov", "webm", "mkv"):
        assert VideoValidator().validate_extension(f"movie.{ext}") == ext


def test_rejects_oversize(temp_env):
    with pytest.raises(ValidationError, match="too large"):
        VideoValidator().validate_size(10 * 1024**3)


def test_sanitize_filename_blocks_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert "/" not in sanitize_filename("a/b\\c.mp4")
    assert sanitize_filename("") == "video"
