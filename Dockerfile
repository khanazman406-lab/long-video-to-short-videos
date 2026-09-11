# ─────────────────────────────────────────────────────────────────────────────
# ClipForge AI — single image = API + built SPA + real FFmpeg video pipeline.
#
#   stage 1 (web-build): node builds frontend/  -> /build/dist
#   stage 2 (runtime):   python + ffmpeg; serves backend/app and frontend/dist
#
# Build from the repo root:
#   docker build -t clipforge-ai .
#   docker run --rm -p 8000:8000 -v clipforge-data:/data clipforge-ai
#
# Works as-is on Render (`runtime: docker`), Railway (`builder: DOCKERFILE`),
# Fly.io / ECS / EC2 / any Docker host, and in CI. Runtime requirements: a
# writable $DATA_DIR (default /data) and, for Postgres, a DATABASE_URL — the
# platform's `postgres://…` string is normalized by app/config.py. See README §15.
# ─────────────────────────────────────────────────────────────────────────────

# ---------- stage 1: build the React app (node) ------------------------------
FROM node:20-alpine AS web-build
WORKDIR /build

# Deps first, so this layer is cached until the manifests change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# Empty = the SPA calls /api on its own origin, which is what this image serves.
# Only set it when hosting the frontend separately from the API.
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- stage 2: API + SPA + ffmpeg (python) -----------------------------
FROM python:3.11-slim-bookworm AS runtime

# DATA_DIR: uploads/thumbnails/exports (mount a volume or a Render disk here).
# FRONTEND_DIST: directory served at / with SPA fallback (see backend/app/utils/spa.py).
# FFMPEG_THREADS: 0 = auto; set 1-2 on small instances. PORT: Render/Railway override it.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data \
    FRONTEND_DIST=/app/frontend/dist \
    FFMPEG_THREADS=0 \
    PORT=8000

# ffmpeg runs the pipeline; the *GL/*X libraries are OpenCV's runtime deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        ca-certificates openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements in their own layer for build-cache friendliness.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

COPY backend/app ./backend/app
COPY --from=web-build /build/dist ./frontend/dist

# Pre-create the data tree; a mounted volume replaces it at runtime.
RUN mkdir -p /data/uploads /data/thumbnails /data/exports /data/temp /data/waveforms \
    && chmod -R 777 /data

EXPOSE 8000

# Used by Docker/ECS/Fly and any image-based health check. Mirrors GET /api/health.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=5)" || exit 1

# One process = API + in-process job pool (WORKER_CONCURRENCY threads), so a
# single service is a complete deployment. Scale with replicas, or move jobs to
# Redis workers (README §15.5). --proxy-headers keeps client IP + https correct
# behind the platform load balancer (that is what the per-IP rate limiter needs).
CMD ["sh", "-c", "exec uvicorn --app-dir backend app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips '*'"]
