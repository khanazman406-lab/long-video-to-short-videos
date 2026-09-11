# ClipForge AI

[![CI](https://github.com/khanazman406-lab/long-video-to-short-videos/actions/workflows/ci.yml/badge.svg)](https://github.com/khanazman406-lab/long-video-to-short-videos/actions/workflows/ci.yml)

> Turn long videos into your best short clips automatically.

ClipForge AI is a production-style full-stack app that analyzes a long video for
high-engagement moments (loud audio, speech, silence breaks, scene changes, fast
cuts, faces, motion, transcript hooks), ranks them with a transparent
**Engagement Score**, and turns the best moments into short-form clips you can
preview, trim, reframe (16:9 / 9:16 / 1:1) and export as MP4/WebM.

To rename the product, change `APP_NAME` in `.env` and `BRAND` in
`frontend/src/lib/brand.ts`.

---

## 1. Project overview

Upload a long video → backend validates it → background job analyzes audio,
scenes, faces, motion and (optionally) speech → candidate moments are scored,
deduplicated and ranked → you get a Top-10 results dashboard with preview, a
trim editor with draggable handles, and single/batch export with aspect-ratio
conversion and face-aware vertical reframing.

No fake scores, no mock exports: every number comes from the real pipeline.

## 2. Features

- Drag-and-drop upload with progress (MP4, MOV, WebM, MKV), streamed to disk
- Validation: extension, MIME hint, size, duration, codec, decodability
- Analysis pipeline: audio energy/speech/silence, scene detection, fast cuts,
  Haar face detection, motion intensity, optional faster-whisper transcripts
- Transparent 0–100 Engagement Score + "why this clip" reasons
- Intelligent candidate windows centered on moments, snapped to scene/silence
  boundaries, overlap-deduplicated
- Results dashboard: thumbnails, scores, reasons, preview / edit / export
- Trim editor: HTML5 player (play, seek, volume, speed, fullscreen), dual-handle
  timeline, MM:SS inputs, save/reset
- Aspect presets: YouTube 16:9, TikTok/Reels/Shorts 9:16, Square 1:1 with
  face-aware auto-reframe for vertical crops
- Export: MP4/WebM, fast/balanced/high presets, single + batch, downloads
- Background jobs (in-process pool by default, Redis-ready), SSE + polling
  progress, project history, dark/light theme, mobile-responsive UI

## 3. Architecture

```
Browser (React + Vite + Tailwind)
  │  /api (JSON, SSE, range-streamed video)
  ▼
FastAPI backend  ── also serves frontend/dist with SPA fallback (one port, one image)
  │  jobs (ThreadPool now, Redis/RQ integration point ready)
  ▼
Analysis pipeline: ffmpeg → audio / scenes / faces / motion / transcript
  → engagement scoring → candidate selection → Top N clips
  ▼
SQLite (dev) / PostgreSQL (prod) + local disk (dev) / S3-ready storage
```

Backend layout (`backend/app/`): `main.py`, `config.py`, `db.py`, `models.py`,
`schemas.py`, `deps.py`, `api/` (health, videos, clips, exports),
`services/` (video, ffmpeg, scene, audio, face, motion, transcript, scorer,
clip_generator, export, storage, analysis_pipeline), `workers/jobs.py`,
`utils/` (logging, security, timecode).

## 4. Requirements

- Python 3.10+ with `venv`
- Node.js 18+ with npm
- FFmpeg: a system `ffmpeg` **or** the bundled binary from
  `pip install imageio-ffmpeg` (auto-detected, no `ffprobe` needed)
- Optional: PostgreSQL 14+, Redis 7+ (production), `faster-whisper` (transcripts)

## 5. Local installation

```bash
git clone <this-repo> && cd <repo>
cp .env.example .env            # optional; defaults work out of the box

# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

Or from the repo root: `npm run install:all` (needs `concurrently` for `npm run dev`:
`npm install` at root first).

## 6. FFmpeg installation

- **Debian/Ubuntu:** `sudo apt-get install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** `winget install FFmpeg` (or choco)
- **No admin / offline apt:** already covered — `imageio-ffmpeg` in
  `requirements.txt` ships a static binary the backend auto-detects.
- Verify: `GET /api/health` reports `"ffmpeg": true`.

## 7. Environment variables

See `.env.example` for the full list: `APP_NAME`, `APP_TAGLINE`, `DATABASE_URL`,
`FRONTEND_DIST`, `REDIS_URL`, `USE_REDIS_QUEUE`, `WORKER_CONCURRENCY`, `STORAGE_*`, `MAX_UPLOAD_SIZE`,
`MAX_VIDEO_DURATION`, `ALLOWED_EXTENSIONS`, `FFMPEG_PATH`, `TRANSCRIPT_*`,
`DEFAULT_NUM_CLIPS`, `MAX_NUM_CLIPS`, `*_CLIP_DURATION`, `EVENT_MERGE_GAP`,
`OVERLAP_THRESHOLD`, `SCORING_WEIGHTS` (JSON), `CLEANUP_TEMP_FILES`,
`RETENTION_DAYS`, `RATE_LIMIT_PER_MINUTE`, `CORS_ORIGINS`, `VITE_API_URL`.

## 8. Database setup

Default is SQLite at `backend/data/clipforge.db` (auto-created on startup, and
the parent directory is created for you). For PostgreSQL:

```bash
# either spelling works — the app rewrites it for SQLAlchemy 2.0
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/clipforge
# DATABASE_URL=postgres://user:pass@localhost:5432/clipforge?sslmode=require
```

`psycopg2-binary` is already in `requirements.txt` (prebuilt wheel: no
`pg_config`, no `libpq-dev`), so `pip install -r backend/requirements.txt` is the
only step. `app/config.py::normalize_database_url` accepts the libpq-style
strings Render, Railway, Neon, Supabase and Heroku print in their dashboards,
trims quotes, keeps `?sslmode=require`, and treats an empty `DATABASE_URL` as
"use SQLite" — so a copy of `.env.example` never breaks startup.

Tables are created automatically. For schema evolution in production, copy
`models.py` into an Alembic project (`alembic init`, `target_metadata =
app.db.Base.metadata`) and generate migrations.

## 9. Redis setup

Optional. The default in-process pool needs nothing. To use Redis:

```bash
docker run -d -p 6379:6379 redis:7-alpine
.venv/bin/pip install redis rq
# .env: REDIS_URL=redis://localhost:6379/0  USE_REDIS_QUEUE=true
```

`workers/jobs.py` pushes `{job_id}` onto `clipforge:jobs`; run one or more
external workers that import the app and call `run_job(job_id)` (documented
integration point in that file). If Redis is unreachable, jobs transparently
fall back to the local pool.

## 10. Running frontend

```bash
cd frontend
npm run dev      # http://localhost:5173 (proxies /api → :8000)
```

For a single-port run instead (what the Docker image does), build once and let
the API serve it:

```bash
npm run build -C frontend                       # → frontend/dist
cd backend && .venv/bin/uvicorn app.main:app --port 8000
# http://localhost:8000 now serves the UI *and* /api
# FRONTEND_DIST=<dir with index.html> overrides the auto-detected location
```

## 11. Running backend

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# API docs: http://localhost:8000/api/docs
# Health:   http://localhost:8000/api/health
```

## 12. Running workers

No separate process needed by default — the job pool lives inside the API
server (`WORKER_CONCURRENCY` threads). For Redis-backed workers, see §9.

## 13. Running tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -x -q
```

Tests generate a synthetic 30 s sample video (color segments + varying audio),
then run health → upload → analyze → clips → edit → 9:16 export → download.
Unit tests cover scoring, candidate centering/dedup, upload validation and the
deploy path (`postgres://` normalization, SPA fallback, asset caching).
The same suite runs on every push/PR in CI — see §15.7.

## 14. Docker setup

Two Dockerfiles, two jobs:

| File | Use it for |
|---|---|
| **`Dockerfile`** (repo root) | **Deployments.** Multi-stage: `node` builds `frontend/` → `python:3.11-slim` + `ffmpeg` runs the API and serves `frontend/dist`. One image, one port, no nginx. Used by Render/Railway and the CI smoke test. |
| `backend/Dockerfile` + `frontend/Dockerfile` | `docker compose up --build` local topology: separate API + nginx static services, plus Postgres and Redis. Handy for trying the split FE/BE deployment. |

```bash
# single image (recommended)
docker build -t clipforge-ai .
docker run --rm -p 8000:8000 \
  -v clipforge-data:/data \
  -e DATABASE_URL=postgresql+psycopg2://clipforge:clipforge@db:5432/clipforge \
  clipforge-ai
# → app on http://localhost:8000, API docs on http://localhost:8000/api/docs

# full compose topology
docker compose up --build
# frontend → http://localhost (nginx, /api proxied to backend)
# backend   → http://localhost:8000
```

The image bundles a real FFmpeg (`apt-get install ffmpeg`) and keeps
`imageio-ffmpeg` as a fallback, so `/api/health` reports `"ffmpeg": true` even
on a base image without it. `/data` is where uploads, thumbnails, waveforms and
exports land — mount a volume or a platform disk there, or point `DATA_DIR` at
object storage via the `StorageBackend` interface.

## 15. Deploying to a public URL

Everything below ships in this repo already: `Dockerfile`, `render.yaml`,
`railway.json`, `.github/workflows/ci.yml`. No build scripts to write, no
`nginx.conf` to edit, no separate static host for the SPA.

### 15.1 What "deployable" means here

```
Dockerfile (root)
  ├─ stage 1: node:20-alpine   npm ci && npm run build     → /build/dist
  └─ stage 2: python:3.11-slim-bookworm + ffmpeg + OpenCV libs
        ├─ backend/app                (FastAPI, job pool, pipeline)
        ├─ frontend/dist              (mounted at / with SPA fallback)
        └─ uvicorn --port ${PORT:-8000} --proxy-headers
```

* **One origin.** The SPA calls `/api/*` on its own origin (`VITE_API_URL` stays
  empty), so there is no CORS, no mixed-content, no second service to keep in
  sync. `CORS_ORIGINS` only matters if you split the frontend onto a CDN.
* **SPA fallback.** `app/utils/spa.py` serves real files first (`/assets/*` with
  `immutable` caching) and answers every other non-`/api` GET with
  `index.html`, so deep links like `/editor/<id>` and refreshes work. Unknown
  `/api/*` paths stay JSON `404`s.
* **Health check.** `GET /api/health` → `{"status":"ok","ffmpeg":true,
  "database":true,...}`. Point every platform's health check at it (already set
  in `render.yaml` and `railway.json`). It returns 200 as soon as the DB answers,
  so a `ffmpeg: false` line shows up as degraded rather than a boot loop.
* **Persistent media.** `DATA_DIR` (default `/data` in the image) must be a real
  disk/volume, otherwise a redeploy deletes every upload and export.
* **Postgres or SQLite.** SQLite works out of the box but is only as durable as
  the volume; on Render/Railway a managed Postgres is one env var away because
  `postgres://…` URLs from these platforms are rewritten to
  `postgresql+psycopg2://…` in `app/config.py` (`psycopg2-binary` is in
  `requirements.txt`). No `libpq-dev`/`pg_config` needed at build time.

### 15.2 Render (Blueprint — fastest path)

`render.yaml` describes the whole stack: **web service (Docker) + Postgres +
Redis + persistent disk**.

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → pick the repo → Render detects
   `render.yaml`.
3. Check the preview (every value — DB, Redis, disk, limits — comes from the
   file, so there is nothing to fill in for a first deploy) → **Apply**.
4. The first deploy builds the image; `https://<name>.onrender.com` then serves
   API and UI together.

Subsequent merges to `main` auto-deploy (`autoDeployTrigger: commit`).

```bash
# or from the CLI (brew install render, or the install script in Render's docs)
render login
render blueprints validate render.yaml
render blueprints launch            # or: render blueprints sync
```

Notes specific to this app:

* **Disk** is mounted at `/data` (`sizeGB: 5`), which is why `DATA_DIR=/data` is
  baked into the image. Increase it in the dashboard; it can grow, never shrink.
* **Instance size.** `plan: starter` is enough to prove it works (single
  analysis job at a time, `WORKER_CONCURRENCY=1`). Video encoding is CPU-bound:
  for real traffic use `1c-2g`+ and keep `WORKER_CONCURRENCY` ≤ vCPU count.
* **`USE_REDIS_QUEUE=false` by default** on purpose: jobs then run inside the web
  process, so a single service is a working deployment. The Redis instance is
  provisioned and wired (`REDIS_URL`) so you can flip it on later — see 15.5.
* **Free-tier Postgres expires after 30 days.** Upgrade `clipforge-db` to
  `basic-256mb` before that; your data stays put, only the plan changes.
* Render's proxy is trusted (`--proxy-headers --forwarded-allow-ips '*'`), so
  rate limiting sees the real client IP and the app knows it is HTTPS.

### 15.3 Railway

`railway.json` tells Railway to build the root `Dockerfile` and to health-check
`/api/health`.

1. Railway → **New Project → Deploy from GitHub repo** (this repo). Railway
   detects the Dockerfile and `railway.json` automatically.
2. **Service → Settings → Networking → Generate domain** to get a public URL.
3. Add a **Volume** (New → Data Storage → Volume) attached to the service with
   mount path **`/data`** — the equivalent of Render's disk. Without it uploads
   vanish on every redeploy.
4. **Provision → PostgreSQL** (and optionally Redis), then reference them in
   the service's **Variables**: `DATABASE_URL=${{Postgres.DATABASE_URL}}`,
   `REDIS_URL=${{Redis.REDIS_URL}}`.
   Railway's internal `postgres://…` string is normalized by the app — paste it
   as-is.
5. Optional but recommended: `MAX_UPLOAD_SIZE=524288000`,
   `WORKER_CONCURRENCY=1`, `RETENTION_DAYS=7`, `TRANSCRIPT_ENABLED=false`.
6. Redeploy. `GET /api/health` should return `{"status":"ok","ffmpeg":true}`.

Railway gives no persistent filesystem by default, so if you skip step 3, set
`DATABASE_URL=sqlite:////data/clipforge.db` only *after* mounting the volume —
otherwise SQLite lives inside the container and resets on each deploy.

```bash
# CLI alternative (needs the railway CLI, not an npm package)
railway login && railway init && railway up
railway variables --set DATABASE_URL="$DATABASE_URL" --set MAX_UPLOAD_SIZE=524288000
railway domain
```

### 15.4 Sizing and limits that actually matter

| Setting | Default | Guidance for a public deploy |
|---|---|---|
| `WORKER_CONCURRENCY` | 2 | ≤ vCPUs. Each analyze job decodes video; 1 on 512 MB/0.1 CPU instances |
| `MAX_UPLOAD_SIZE` | 2 GB | Match your disk and proxy limit (Render/Railway bodies are also capped) |
| `MAX_VIDEO_DURATION` | 3 h | Lower it (e.g. 3600) until you have CPU headroom |
| `DEFAULT_NUM_CLIPS` / `MAX_NUM_CLIPS` | 10 / 20 | Fewer clips = much faster first results |
| `RETENTION_DAYS` + `CLEANUP_TEMP_FILES` | 30 / true | Public demo: 7 days and `true` |
| `TRANSCRIPT_ENABLED` | true | `false` unless you install `faster-whisper`; the model is ~80 MB and slow on small instances |
| `RATE_LIMIT_PER_MINUTE` | 120 | Lower (e.g. 30) for an open signup-free demo |
| disk at `DATA_DIR` | 5 GB | Raw upload + exports both land here; budget ~1 GB per hour of 1080p source |
| instance RAM | — | OpenCV + numpy decode frames; 1 GB minimum, 2 GB comfortable |

### 15.5 Scaling out (optional)

The default topology is one process: uvicorn + an in-process thread pool. To
separate web from heavy renders:

```bash
# 1. both services build the same image
# 2. web:      USE_REDIS_QUEUE=true  (enqueue only)
# 3. worker:   USE_REDIS_QUEUE=false REDIS_URL=… and
#              python -c "from app.workers.jobs import run_job; …"  (see §9)
```

`app/workers/jobs.py` is the documented integration point: the web process
pushes job ids to Redis, workers pop them and call `run_job(job_id)`; progress
and results are persisted on the DB rows, so the browser keeps streaming via SSE
either way. If Redis is unreachable the job falls back to the local pool — the
app never hangs waiting for a queue.

### 15.6 VPS / behind your own nginx

```bash
sudo apt-get install -y docker.io
docker build -t clipforge-ai .
docker run -d --name clipforge --restart unless-stopped \
  -p 127.0.0.1:8000:8000 -v /srv/clipforge/data:/data \
  -e DATABASE_URL=postgresql+psycopg2://… -e CORS_ORIGINS=https://clip.example.com \
  clipforge-ai
```

```nginx
server {
  listen 443 ssl http2;
  server_name clip.example.com;
  client_max_body_size 2048m;          # keep ≥ MAX_UPLOAD_SIZE
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;               # SSE progress streaming
    proxy_read_timeout 3600s;          # long uploads + exports
  }
}
```

No SPA-fallback rules are needed — FastAPI already answers client-side routes.
Only add `try_files $uri /index.html` if you serve `frontend/dist` from a pure
static host instead.

### 15.7 Continuous integration

`.github/ci.yml` runs on every push to `main` and on every PR — after one
activation step, because GitHub only executes files in `.github/workflows/` and
deploy tokens often cannot write there:

```bash
git mv .github/ci.yml .github/workflows/ci.yml
git commit -m "ci: activate GitHub Actions workflow" && git push
```

* **Backend (pytest)** — unit + the full pipeline test (upload → analyze →
  clips → trim → 9:16 export → download) against real FFmpeg.
* **Frontend** — `tsc --noEmit && vite build`, uploads `frontend/dist` as an
  artifact.
* **Deploy config** — parses `render.yaml`, `docker-compose.yml`,
  `railway.json`, `package.json` and asserts they still point at real files,
  `/api/health`, `/data` and the right Postgres/Redis services (so a renamed
  service can't silently break a blueprint).
* **Docker image smoke test** — builds the *root* `Dockerfile` (the exact thing
  Render/Railway build), starts it with a volume at `/data`, then asserts:
  health is `ffmpeg:true/database:true`, `/`, `/results` and `/editor/<id>`
  return the SPA shell, hashed assets are `immutable`, unknown `/api/*` is a
  JSON 404, and `/data/uploads` exists on the mount.

Merge to `main` → Render auto-deploys (Blueprint) and Railway redeploys (if
"Auto Deploy" is on). To also publish the image to a registry, add a `deploy`
job that runs

```bash
docker buildx build --push -t ghcr.io/<owner>/clipforge:${GITHUB_SHA} .
```

after `docker login` with `GITHUB_TOKEN` — nothing else in the repo needs to
change.

### 15.8 Deploy troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ArgumentError: Could not parse SQLAlchemy URL` | Pre-15 fix: platform `postgres://` URL. Now normalized in `app/config.py`; check you are on this commit and that `DATABASE_URL` is a full URL (`psql -c ...` style strings won't parse) |
| `ModuleNotFoundError: psycopg2` | You removed `psycopg2-binary` from `requirements.txt`, or you are building an old `backend/`-only image without `pip install psycopg2-binary` |
| CI never runs | Workflow is still at `.github/ci.yml` — `git mv` it into `.github/workflows/` (see §15.7); GitHub rejects pushes to that dir from tokens without the `workflows` permission |
| Boot loop `database is locked` / no `/data` writes | Volume/disk not mounted at `DATA_DIR`; Render disk `mountPath` must be `/data` |
| 502 right after deploy | Health check path missing: it must be `/api/health` (not `/`); give slow cold starts `healthcheckTimeout` ≥ 300 s |
| Deep links 404 on refresh | The frontend is being served by another host (nginx/S3/Vercel) without a `/index.html` fallback, or `FRONTEND_DIST` points at a dir with no `index.html` (the log says `serving frontend from …` when it is mounted) |
| Upload fails at ~500 MB | `MAX_UPLOAD_SIZE`, proxy `client_max_body_size`, or the disk is full |
| Analysis never finishes | `WORKER_CONCURRENCY=0`/instance OOM-killed. Drop `MAX_VIDEO_DURATION`, run on a bigger plan, or 15.5 |


## 16. Troubleshooting

| Symptom | Fix |
|---|---|
| `/api/health` → `ffmpeg: false` | Install system ffmpeg or `pip install imageio-ffmpeg`; set `FFMPEG_PATH` |
| "Video could not be decoded" | File is corrupt or an unsupported codec — try re-exporting as H.264 MP4 |
| Analysis stuck at 0% | Check backend logs; ensure `DATA_DIR` is writable and disk isn't full |
| Transcripts always empty | `pip install faster-whisper` (pulls a ~80 MB tiny model on first use) |
| Upload fails for large files | Raise `MAX_UPLOAD_SIZE` and proxy body limits; check disk space |
| Frontend can't reach API | In dev, Vite proxies `/api`; in prod set `VITE_API_URL` + `CORS_ORIGINS` |

## 17. Production recommendations

- Managed PostgreSQL + Redis, persistent object storage (S3/R2) via the
  `StorageBackend` interface, CDN for exports
- Enable authentication in `app/deps.py:get_current_user` (JWT/session) and put
  the API behind HTTPS + a WAF
- Tune `SCORING_WEIGHTS`, `EVENT_MERGE_GAP`, `OVERLAP_THRESHOLD` per content
  niche; add `faster-whisper` or a GPU box for transcripts
- Set `RETENTION_DAYS` + a cron cleanup for uploads/exports (privacy)
- Ship `backend/data` outside the container, back up the DB, and scrape logs
  (`job_finished`, `analysis_completed`) for monitoring
