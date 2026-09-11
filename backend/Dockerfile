# ClipForge AI — backend + worker image with a real video pipeline.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 libxext6 libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
RUN mkdir -p /data/uploads /data/thumbnails /data/exports /data/temp /data/waveforms

EXPOSE 8000
# The local job pool runs inside this process; scale workers by adding
# replicas or pointing USE_REDIS_QUEUE at a shared Redis (see README).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
