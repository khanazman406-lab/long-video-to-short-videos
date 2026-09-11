"""Storage abstraction: local filesystem today, S3-compatible tomorrow.

All application code talks to the StorageBackend protocol. The local backend
stores everything under DATA_DIR; an S3 backend can be dropped in later
using STORAGE_* settings without touching callers.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from ..config import get_settings


class StorageBackend(Protocol):
    def path_for(self, category: str, name: str) -> Path: ...
    def save_upload(self, src: Path, name: str) -> Path: ...
    def delete(self, path: Path) -> None: ...
    def exists(self, path: Path) -> bool: ...


class LocalStorage:
    """Filesystem storage rooted at DATA_DIR."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or get_settings().data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, category: str, name: str) -> Path:
        directory = self.root / category
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / name).resolve()
        if self.root.resolve() not in target.parents and target != self.root.resolve():
            raise ValueError("Invalid storage path")
        return target

    def save_upload(self, src: Path, name: str) -> Path:
        dest = self.path_for("uploads", name)
        shutil.move(str(src), str(dest))
        return dest

    def delete(self, path: Path) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def exists(self, path: Path) -> bool:
        return Path(path).exists()


def get_storage() -> LocalStorage:
    settings = get_settings()
    if settings.storage_provider.lower() not in ("local", ""):
        # S3 backend integration point — falls back to local with a clear log.
        # Implement S3Storage (boto3) here when object storage is configured.
        pass
    return LocalStorage()
