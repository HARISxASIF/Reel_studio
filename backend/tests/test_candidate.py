import pytest
from app.services.candidate import (
    calculate_overlap_ratio,
    deduplicate_candidates,
    build_clip_subtitles,
)


def test_calculate_overlap_ratio():
    # Identical intervals
    assert calculate_overlap_ratio(10.0, 40.0, 10.0, 40.0) == 1.0

    # No overlap
    assert calculate_overlap_ratio(0.0, 30.0, 40.0, 70.0) == 0.0

    # Partial overlap (10s overlap, union 50s)
    assert round(calculate_overlap_ratio(0.0, 30.0, 20.0, 50.0), 3) == round(10.0 / 50.0, 3)


def test_deduplicate_candidates():
    candidates = [
        {
            "start_time": 10.0,
            "end_time": 45.0,
            "overall_score": 75.0,
            "top_caption": "LOWER SCORE VERSION",
        },
        {
            "start_time": 12.0,
            "end_time": 47.0,
            "overall_score": 92.0,
            "top_caption": "HIGHER SCORE VERSION",
        },
        {
            "start_time": 100.0,
            "end_time": 135.0,
            "overall_score": 80.0,
            "top_caption": "DISTINCT MOMENT",
        },
    ]

    deduped = deduplicate_candidates(candidates, iou_threshold=0.5)

    # Must retain higher score version (92.0) and distinct moment (80.0)
    assert len(deduped) == 2
    captions = [d["top_caption"] for d in deduped]
    assert "HIGHER SCORE VERSION" in captions
    assert "DISTINCT MOMENT" in captions
    assert "LOWER SCORE VERSION" not in captions


def test_build_clip_subtitles_timing_conversion():
    full_transcript = [
        {"word": "Before", "start": 5.0, "end": 5.5, "prob": 0.99},
        {"word": "First", "start": 10.2, "end": 10.6, "prob": 0.98},
        {"word": "Second", "start": 11.0, "end": 11.4, "prob": 0.95},
        {"word": "After", "start": 50.0, "end": 50.5, "prob": 0.99},
    ]

    clip_start = 10.0
    clip_end = 40.0

    subtitles = build_clip_subtitles(full_transcript, clip_start, clip_end)

    # Only "First" and "Second" should be included
    assert len(subtitles) == 2
    assert subtitles[0]["word"] == "First"
    # 10.2 - 10.0 = 0.2
    assert subtitles[0]["start"] == 0.2
    assert subtitles[0]["end"] == 0.6

    assert subtitles[1]["word"] == "Second"
    # 11.0 - 10.0 = 1.0
    assert subtitles[1]["start"] == 1.0
    assert subtitles[1]["end"] == 1.4
