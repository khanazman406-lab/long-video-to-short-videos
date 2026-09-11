"""API integration tests: health -> upload -> analyze -> clips -> edit -> export."""

from __future__ import annotations

import time


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["ffmpeg"] is True
    assert body["database"] is True


def test_upload_rejects_bad_format(client):
    r = client.post("/api/videos/upload", files={"file": ("evil.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]


def test_full_pipeline(client, sample_video):
    # Upload
    with open(sample_video, "rb") as f:
        r = client.post("/api/videos/upload", files={"file": ("sample.mp4", f, "video/mp4")})
    assert r.status_code == 201, r.text
    video = r.json()
    assert video["duration"] > 20
    vid = video["id"]

    # Analyze (small clip counts for speed)
    r = client.post(f"/api/videos/{vid}/analyze", json={"clip_duration": 10, "num_clips": 3})
    assert r.status_code == 202, r.text

    # Wait for completion (local pool runs in-process)
    deadline = time.time() + 300
    status = ""
    while time.time() < deadline:
        s = client.get(f"/api/videos/{vid}/status").json()
        status = s["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(2)
    assert status == "completed", s

    # Clips
    r = client.get(f"/api/videos/{vid}/clips")
    assert r.status_code == 200
    clips = r.json()["clips"]
    assert 1 <= len(clips) <= 3
    clip = clips[0]
    assert clip["score"] >= 0
    assert clip["end_time"] > clip["start_time"]

    # Edit trim points
    new_end = min(video["duration"], clip["start_time"] + 5)
    r = client.put(f"/api/clips/{clip['id']}", json={"end_time": new_end})
    assert r.status_code == 200, r.text
    assert abs(r.json()["end_time"] - new_end) < 0.01

    # Export one clip (fast preset path via balanced default is fine for 5s)
    r = client.post(
        f"/api/clips/{clip['id']}/export",
        json={"aspect_ratio": "9:16", "output_format": "mp4", "quality": "fast"},
    )
    assert r.status_code == 202, r.text
    export_id = r.json()["id"]

    deadline = time.time() + 300
    estate = ""
    while time.time() < deadline:
        e = client.get(f"/api/exports/{export_id}").json()
        estate = e["status"]
        if estate in ("completed", "failed"):
            break
        time.sleep(2)
    assert estate == "completed", e

    # Download
    r = client.get(f"/api/exports/{export_id}/download")
    assert r.status_code == 200
    assert len(r.content) > 10_000
    assert r.headers["content-type"] == "video/mp4"
