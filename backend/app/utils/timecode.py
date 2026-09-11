"""Time formatting helpers."""

from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


def format_range(start: float, end: float) -> str:
    return f"{format_timestamp(start)} → {format_timestamp(end)}"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
