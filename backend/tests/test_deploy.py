"""Deploy-path tests: DATABASE_URL normalization, SPA serving, container config.

These guard the pieces the Render/Railway/Docker deployment depends on:
libpq URLs from the platforms, the single-image frontend mount with
client-side-route fallback, and the health endpoint used as the health check.
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------
# postgres:// normalization
# --------------------------------------------------------------------------
def test_normalize_postgres_scheme_variants():
    from app.config import normalize_database_url

    for scheme in ("postgres", "postgresql", "POSTGRES"):
        out = normalize_database_url(f"{scheme}://user:pass@host:5432/db")
        assert out == "postgresql+psycopg2://user:pass@host:5432/db"


def test_normalize_keeps_query_string_and_dsn_details():
    from app.config import normalize_database_url

    url = "postgres://clipforge:p%40ss@dpg-xyz.a.oregon.postgres.render.com:5432/clipforge?sslmode=require"
    out = normalize_database_url(url)
    assert out.startswith("postgresql+psycopg2://")
    assert out.endswith("/clipforge?sslmode=require")
    assert "p%40ss" in out  # credentials are not mangled


def test_normalize_strips_quotes_and_blank_values():
    from app.config import DEFAULT_SQLITE_URL, normalize_database_url

    assert normalize_database_url('  "postgres://u:p@h:5432/d"  ') == "postgresql+psycopg2://u:p@h:5432/d"
    assert normalize_database_url("") == DEFAULT_SQLITE_URL
    assert normalize_database_url(None) == DEFAULT_SQLITE_URL


def test_normalize_leaves_explicit_drivers_and_sqlite_alone():
    from app.config import normalize_database_url

    assert normalize_database_url("sqlite:///./data/x.db") == "sqlite:///./data/x.db"
    assert (
        normalize_database_url("postgresql+asyncpg://u:p@h:5432/d")
        == "postgresql+asyncpg://u:p@h:5432/d"
    )
    assert (
        normalize_database_url("postgresql+psycopg2://u:p@h:5432/d")
        == "postgresql+psycopg2://u:p@h:5432/d"
    )


def test_settings_normalize_env_database_url(monkeypatch, tmp_path):
    from app import config as config_mod

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db.internal:5432/clipforge")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    config_mod.get_settings.cache_clear()
    try:
        settings = config_mod.get_settings()
        assert settings.database_url == "postgresql+psycopg2://u:p@db.internal:5432/clipforge"
        assert settings.is_postgres() is True
    finally:
        config_mod.get_settings.cache_clear()


def test_sqlalchemy_accepts_platform_urls(tmp_path):
    """The normalized URL must parse for SQLAlchemy (this is what used to crash)."""
    from sqlalchemy.engine import make_url

    from app.config import normalize_database_url

    url = make_url(normalize_database_url("postgres://u:p@localhost:5432/db?sslmode=require"))
    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "u" and url.password == "p"
    assert url.host == "localhost" and url.database == "db"
    assert url.query == {"sslmode": "require"}


def test_engine_creates_missing_sqlite_directory(tmp_path, monkeypatch):
    from app import config as config_mod
    from app import db as db_mod

    nested = tmp_path / "does" / "not" / "exist" / "clipforge.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{nested}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    config_mod.get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    try:
        db_mod.init_db()  # must not fail just because the folder is missing
        assert nested.exists()
    finally:
        config_mod.get_settings.cache_clear()
        db_mod._engine = None
        db_mod._SessionLocal = None


# --------------------------------------------------------------------------
# frontend/dist served by FastAPI
# --------------------------------------------------------------------------
@pytest.fixture()
def spa_env(monkeypatch, tmp_path):
    """App wired to a fake built frontend + isolated sqlite/data dir."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><head><title>t</title></head>'
        '<body><div id="root"></div><script src="/assets/index-abc123.js"></script></body></html>'
    )
    (dist / "assets" / "index-abc123.js").write_text("console.log('clipforge');\n")

    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'spa.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    from app import config as config_mod
    from app import db as db_mod

    config_mod.get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    try:
        with TestClient(create_app()) as client_obj:
            yield client_obj
    finally:
        config_mod.get_settings.cache_clear()
        db_mod._engine = None
        db_mod._SessionLocal = None


def test_spa_root_and_deep_links(spa_env):
    for path in ("/", "/results", "/editor/some-video-id", "/nope/not/a/file"):
        r = spa_env.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert '<div id="root">' in r.text
        assert r.headers["content-type"].startswith("text/html")
        assert r.headers["cache-control"] == "no-cache"


def test_spa_assets_served_with_immutable_cache(spa_env):
    r = spa_env.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert "clipforge" in r.text
    assert "immutable" in r.headers["cache-control"]


def test_api_still_wins_over_frontend_and_404s_are_json(spa_env):
    assert spa_env.get("/api/health").status_code == 200
    missing = spa_env.get("/api/does-not-exist")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Not Found"}
    assert spa_env.get("/api/docs").status_code == 200


def test_frontend_never_escapes_the_dist_dir(spa_env):
    # Traversal attempts must not read files outside the built SPA directory.
    for path in ("/%2e%2e/%2e%2e/etc/passwd", "/..%2f..%2fetc/passwd", "/assets/../../etc/passwd"):
        r = spa_env.get(path)
        assert "root:" not in r.text, f"{path} leaked /etc/passwd"
        assert r.status_code in (200, 400, 403, 404)
    r = spa_env.get("/index.html")
    assert r.status_code == 200  # real file, served directly


def test_api_only_when_no_build_present(monkeypatch, tmp_path):
    from app import config as config_mod

    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing-dist"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    config_mod.get_settings.cache_clear()
    try:
        assert config_mod.get_settings().resolved_frontend_dist() is None
    finally:
        config_mod.get_settings.cache_clear()


def test_health_payload_matches_readme_contract(spa_env):
    body = spa_env.get("/api/health").json()
    assert set(body) >= {"status", "app", "ffmpeg", "database", "queue", "transcript_engine"}
    assert body["ffmpeg"] is True  # the image installs ffmpeg
