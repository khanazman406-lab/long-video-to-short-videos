# ClipForge AI

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
FastAPI backend
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

See `.env.example` for the full list: `APP_NAME`, `DATABASE_URL`, `REDIS_URL`,
`USE_REDIS_QUEUE`, `WORKER_CONCURRENCY`, `STORAGE_*`, `MAX_UPLOAD_SIZE`,
`MAX_VIDEO_DURATION`, `ALLOWED_EXTENSIONS`, `FFMPEG_PATH`, `TRANSCRIPT_*`,
`DEFAULT_NUM_CLIPS`, `MAX_NUM_CLIPS`, `*_CLIP_DURATION`, `EVENT_MERGE_GAP`,
`OVERLAP_THRESHOLD`, `SCORING_WEIGHTS` (JSON), `CLEANUP_TEMP_FILES`,
`RETENTION_DAYS`, `RATE_LIMIT_PER_MINUTE`, `CORS_ORIGINS`, `VITE_API_URL`.

## 8. Database setup

Default is SQLite at `backend/data/clipforge.db` (auto-created on startup).
For PostgreSQL:

```bash
# DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/clipforge
.venv/bin/pip install psycopg2-binary
```

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
Unit tests cover scoring, candidate centering/dedup and upload validation.

## 14. Docker setup

```bash
docker compose up --build
# frontend → http://localhost (nginx, /api proxied to backend)
# backend   → http://localhost:8000
```

`backend/Dockerfile` bundles Python + FFmpeg + OpenCV deps and runs the real
pipeline. `docker-compose.yml` also shows the PostgreSQL + Redis production
topology.

## 15. Deployment

- **Frontend:** any static host (the `frontend/Dockerfile` + `nginx.conf` pair
  works on Railway/Render/Fly; for GitHub Pages, set `VITE_API_URL` to your
  public API origin and add it to `CORS_ORIGINS`).
- **Backend:** Railway/Render/Fly/Docker host with `DATABASE_URL` (managed
  Postgres), persistent disk or S3 for `DATA_DIR`, and `REDIS_URL` for queued
  workers. Set `WORKER_CONCURRENCY` to match vCPU/RAM.
- Serve the API over HTTPS; keep `MAX_UPLOAD_SIZE` in sync with your proxy's
  `client_max_body_size`.

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
