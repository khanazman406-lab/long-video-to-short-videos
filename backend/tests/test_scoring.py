"""Engagement scoring + candidate generation unit tests."""

from __future__ import annotations

from app.services import clip_generator as cg
from app.services.engagement_scorer import WeightedEngagementScorer
from app.services.interfaces import (
    AudioFeatures,
    FaceObservation,
    MotionFeatures,
    SceneEvent,
    TranscriptSegment,
)


def _audio(n=60):
    return AudioFeatures(
        times=[i * 0.5 for i in range(n)],
        rms=[0.5] * n,
        peak=[0.6] * n,
        energy=[0.9 if 20 <= i < 30 else 0.3 for i in range(n)],
        speech=[0.8 if 20 <= i < 30 else 0.2 for i in range(n)],
        silence=[False] * n,
        loud_moments=[12.5],
        silence_breaks=[15.0],
        window=0.5,
    )


def _motion(n=60):
    return MotionFeatures(
        times=[i * 0.5 for i in range(n)],
        intensity=[0.8 if 20 <= i < 30 else 0.2 for i in range(n)],
        window=0.5,
    )


def test_scorer_ranks_hot_window_highest():
    scorer = WeightedEngagementScorer()
    audio = _audio()
    motion = _motion()
    scenes = [SceneEvent(time=12.0, strength=0.9)]
    faces = [FaceObservation(time=12.0, count=1, boxes=[(10, 10, 50, 50)], frame_width=320, frame_height=180)]
    out = scorer.score_windows(30.0, 1.0, audio, scenes, faces, motion, [])
    assert len(out) == 30
    best = max(out, key=lambda w: w["score"])
    assert 10 <= best["start"] <= 15, best
    assert best["score"] > 20
    assert isinstance(best["reasons"], list) and len(best["reasons"]) > 0


def test_transcript_hook_boosts_signal():
    scorer = WeightedEngagementScorer()
    audio = _audio()
    motion = _motion()
    segs = [TranscriptSegment(start=12.0, end=14.0, text="Really? The secret truth!", score=0.9)]
    out = scorer.score_windows(30.0, 1.0, audio, [], [], motion, segs)
    hot = [w for w in out if 12 <= w["start"] < 14]
    cold = [w for w in out if 25 <= w["start"] < 27]
    assert hot and cold
    assert hot[0]["signals"]["transcript_signal"] > 0.5
    assert cold[0]["signals"]["transcript_signal"] == 0.0


def test_candidate_centering_and_dedup():
    scorer = WeightedEngagementScorer()
    audio = _audio()
    motion = _motion()
    scenes = [SceneEvent(time=12.0, strength=0.9)]
    windows = scorer.score_windows(60.0, 1.0, audio, scenes, [], motion, [])
    top = cg.select_top_clips(60.0, 30.0, 3, windows, audio, scenes, [])
    assert len(top) >= 1
    # The exciting moment (~12s) should be INSIDE the clip, not at its start.
    assert top[0].start < 12.0 < top[0].end
    # Overlap filtering: no two clips mostly overlapping.
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            assert cg.overlap_ratio(top[i], top[j]) < 0.9


def test_overlap_ratio_math():
    a = cg.Candidate(0, 30, 90, [], {}, 15)
    b = cg.Candidate(5, 35, 80, [], {}, 20)
    assert cg.overlap_ratio(a, b) > 0.5
    c = cg.Candidate(100, 130, 70, [], {}, 115)
    assert cg.overlap_ratio(a, c) == 0.0
