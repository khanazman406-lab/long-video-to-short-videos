"""Candidate generation: events -> merged moments -> centered windows -> top N.

Instead of scanning every second as an independent clip, the pipeline:
  1. Collects event timestamps (loud moments, silence breaks, scene cuts,
     transcript hooks, score peaks).
  2. Merges nearby events into "moments" (config EVENT_MERGE_GAP).
  3. Centers a candidate window of the requested duration on each moment,
     snapped to scene/silence boundaries and clamped to the video.
  4. Scores each candidate from its window scores + boundary bonuses.
  5. Removes overlapping duplicates (OVERLAP_THRESHOLD) keeping the best.
  6. Ranks and returns the top N.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from ..utils.logging import get_logger
from .interfaces import AudioFeatures, SceneEvent, TranscriptSegment

logger = get_logger(__name__)


@dataclass
class Candidate:
    start: float
    end: float
    score: float
    reasons: list[str]
    signals: dict
    peak_time: float


def collect_events(
    scored_windows: list[dict],
    audio: AudioFeatures,
    scenes: list[SceneEvent],
    transcripts: list[TranscriptSegment],
    top_fraction: float = 0.25,
) -> list[tuple[float, float]]:
    """Return (time, weight) event list from every signal source."""
    events: list[tuple[float, float]] = []
    for t in audio.loud_moments:
        events.append((t, 1.0))
    for t in audio.silence_breaks:
        events.append((t, 0.7))
    for s in scenes:
        events.append((s.time, 0.5 + 0.5 * s.strength))
    for seg in transcripts:
        if seg.score >= 0.4:
            events.append(((seg.start + seg.end) / 2, 0.4 + 0.6 * seg.score))
    # Score peaks: windows in the top quartile that are local maxima.
    scores = [w["score"] for w in scored_windows]
    if scores:
        threshold = sorted(scores)[max(0, int(len(scores) * (1 - top_fraction)) - 1)]
        for i, w in enumerate(scored_windows):
            prev_s = scores[i - 1] if i > 0 else -1
            next_s = scores[i + 1] if i + 1 < len(scores) else -1
            if w["score"] >= threshold and w["score"] >= prev_s and w["score"] >= next_s:
                center = (w["start"] + w["end"]) / 2
                events.append((center, 0.6 + 0.4 * min(1.0, w["score"] / 100)))
    # Fallback: spread events evenly so short/flat videos still get clips.
    if not events and scored_windows:
        duration = scored_windows[-1]["end"]
        for k in range(5):
            events.append((duration * (k + 1) / 6, 0.3))
    return sorted(events)


def merge_events(events: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    """Merge events closer than *gap* seconds into weighted moment centers."""
    if not events:
        return []
    clusters: list[list[tuple[float, float]]] = [[events[0]]]
    for t, w in events[1:]:
        if t - clusters[-1][-1][0] <= gap:
            clusters[-1].append((t, w))
        else:
            clusters.append([(t, w)])
    moments = []
    for cluster in clusters:
        total_w = sum(w for _, w in cluster) or 1.0
        center = sum(t * w for t, w in cluster) / total_w
        moments.append((round(center, 2), round(total_w / len(cluster), 3)))
    return sorted(moments)


def snap_to_boundaries(
    start: float,
    end: float,
    scene_times: list[float],
    silence_times: list[float],
    max_shift: float = 2.5,
) -> tuple[float, float]:
    """Nudge boundaries toward the nearest scene cut / silence edge."""
    for boundary_list in (scene_times, silence_times):
        if not boundary_list:
            continue
        start = _snap_one(start, boundary_list, max_shift)
        end = _snap_one(end, boundary_list, max_shift)
    return start, end


def _snap_one(t: float, candidates: list[float], max_shift: float) -> float:
    best = min(candidates, key=lambda c: abs(c - t), default=None)
    if best is not None and abs(best - t) <= max_shift:
        return round(best, 2)
    return t


def build_candidates(
    duration: float,
    clip_duration: float,
    scored_windows: list[dict],
    moments: list[tuple[float, float]],
    scene_times: list[float],
    silence_times: list[float],
) -> list[Candidate]:
    settings = get_settings()
    clip_len = min(max(clip_duration, settings.min_clip_duration), settings.max_clip_duration)
    clip_len = min(clip_len, duration)
    if clip_len <= 0:
        return []

    candidates: list[Candidate] = []
    for center, weight in moments:
        # Intelligently center the window on the moment (not moment -> +N).
        start = center - clip_len / 2
        end = start + clip_len
        # Clamp into the video.
        if start < 0:
            start, end = 0.0, clip_len
        if end > duration:
            end, start = duration, max(0.0, duration - clip_len)
        start, end = snap_to_boundaries(start, end, scene_times, silence_times)
        # Re-clamp after snapping and enforce minimum length.
        start = max(0.0, start)
        end = min(duration, end)
        if end - start < clip_len * 0.7:
            start = max(0.0, min(start, duration - clip_len))
            end = min(duration, start + clip_len)

        covered = [w for w in scored_windows if w["end"] > start and w["start"] < end]
        if covered:
            avg_score = sum(w["score"] for w in covered) / len(covered)
            peak_score = max(w["score"] for w in covered)
            score = 0.65 * avg_score + 0.35 * peak_score
            # Boundary bonus: starting near a scene cut / speech break.
            if any(abs(s - start) <= 2.0 for s in scene_times):
                score += 3.0
            if any(abs(s - start) <= 2.0 for s in silence_times):
                score += 2.0
            score = min(100.0, score + weight * 2.0)
            reason_counts: dict[str, int] = {}
            for w in covered:
                for r in w["reasons"]:
                    reason_counts[r] = reason_counts.get(r, 0) + 1
            reasons = sorted(reason_counts, key=lambda r: -reason_counts[r])[:6]
            signals = {
                k: round(sum(w["signals"].get(k, 0) for w in covered) / len(covered), 3)
                for k in (covered[0]["signals"] if covered else {})
            }
        else:
            score, reasons, signals = 10.0, [], {}
        candidates.append(
            Candidate(
                start=round(start, 2),
                end=round(end, 2),
                score=round(score, 1),
                reasons=reasons,
                signals=signals,
                peak_time=center,
            )
        )
    return candidates


def overlap_ratio(a: Candidate, b: Candidate) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    union = max(a.end, b.end) - min(a.start, b.start)
    return inter / union if union > 0 else 0.0


def deduplicate(candidates: list[Candidate], threshold: float | None = None) -> list[Candidate]:
    """Greedy overlap filtering: keep the highest-scoring of each overlap group."""
    threshold = get_settings().overlap_threshold if threshold is None else threshold
    ranked = sorted(candidates, key=lambda c: -c.score)
    kept: list[Candidate] = []
    for cand in ranked:
        if all(overlap_ratio(cand, other) < threshold for other in kept):
            kept.append(cand)
    return kept


def select_top_clips(
    duration: float,
    clip_duration: float,
    num_clips: int,
    scored_windows: list[dict],
    audio: AudioFeatures,
    scenes: list[SceneEvent],
    transcripts: list[TranscriptSegment],
) -> list[Candidate]:
    settings = get_settings()
    events = collect_events(scored_windows, audio, scenes, transcripts)
    moments = merge_events(events, settings.event_merge_gap)
    scene_times = sorted(s.time for s in scenes)
    silence_times = sorted(audio.silence_breaks)
    candidates = build_candidates(duration, clip_duration, scored_windows, moments, scene_times, silence_times)
    deduped = deduplicate(candidates)
    top = sorted(deduped, key=lambda c: -c.score)[: max(1, min(num_clips, settings.max_num_clips))]
    # Guarantee coverage: if dedup left too few, fill from ranked remainder.
    if len(top) < min(num_clips, len(candidates)):
        chosen = {(c.start, c.end) for c in top}
        for cand in sorted(candidates, key=lambda c: -c.score):
            if (cand.start, cand.end) not in chosen:
                top.append(cand)
                chosen.add((cand.start, cand.end))
            if len(top) >= num_clips:
                break
        top = sorted(top, key=lambda c: -c.score)[:num_clips]
    logger.info("selected %d clips from %d candidates (%d moments)", len(top), len(candidates), len(moments))
    return top
