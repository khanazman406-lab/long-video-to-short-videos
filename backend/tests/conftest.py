"""Pytest fixtures: isolated temp DB + sample video generation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import imageio_ffmpeg  # noqa: E402

TMP = BACKEND / "tests" / ".tmp"


def ffmpeg_exe() -> str:
    return os.environ.get("FFMPEG_PATH") or imageio_ffmpeg.get_ffmpeg_exe()


@pytest.fixture(scope="session")
def sample_video() -> Path:
    """Generate a 30s synthetic video with scene changes + varying audio."""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / "sample.mp4"
    if out.exists() and out.stat().st_size > 100_000:
        return out
    exe = ffmpeg_exe()
    # 3 x 10s segments, different colors + audio energy, concatenated.
    parts = []
    colors = ["red", "blue", "green"]
    for i, color in enumerate(colors):
        part = TMP / f"part{i}.mp4"
        freq = 440 + i * 220
        vol = 0.3 + i * 0.3
        subprocess.run(
            [
                exe, "-y",
                "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=30:duration=10",
                "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=10,volume={vol}",
                "-vf", f"drawbox=c={color}:t=fill",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(part),
            ],
            capture_output=True,
            check=True,
            timeout=300,
        )
        parts.append(part)
    with open(TMP / "concat.txt", "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run(
        [exe, "-y", "-f", "concat", "-safe", "0", "-i", str(TMP / "concat.txt"),
         "-c", "copy", str(out)],
        capture_output=True,
        check=True,
        timeout=300,
    )
    return out


@pytest.fixture()
def temp_env(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    # Reset cached settings + engine singletons.
    from app import config as config_mod
    from app import db as db_mod

    config_mod.get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    config_mod.get_settings().ensure_data_dirs()
    db_mod.init_db()
    yield {"db": str(db_path), "data": str(data_dir)}
    config_mod.get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None


@pytest.fixture()
def client(temp_env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
