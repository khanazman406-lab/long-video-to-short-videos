"""Security helpers: filename sanitization, validation errors."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


class ValidationError(ValueError):
    """User-facing validation failure (safe message, no stack trace)."""


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """Strip path components and unsafe characters from a user filename."""
    base = Path(name).name  # drop any directory traversal
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not base:
        base = "video"
    if len(base) > max_length:
        stem, dot, ext = base.rpartition(".")
        if dot and len(ext) <= 8:
            base = stem[: max_length - len(ext) - 1] + "." + ext
        else:
            base = base[:max_length]
    return base


def ensure_within_directory(path: Path, directory: Path) -> Path:
    """Resolve and verify *path* stays inside *directory* (traversal guard)."""
    resolved = path.resolve()
    base = directory.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValidationError("Invalid file path.")
    return resolved
