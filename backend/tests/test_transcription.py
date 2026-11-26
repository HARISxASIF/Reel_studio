import pytest
from app.services.transcription import reconcile_transcript_words


def test_reconcile_transcript_words():
    # Chunk 0 words (0s to 345s)
    chunk0_words = [
        {"word": "Hello", "start": 10.0, "end": 10.5, "prob": 0.99},
        {"word": "world", "start": 10.6, "end": 11.0, "prob": 0.99},
        # In overlap window (300s to 345s)
        {"word": "Overlap1", "start": 310.0, "end": 310.5, "prob": 0.95},
        {"word": "Overlap2", "start": 330.0, "end": 330.5, "prob": 0.95},
    ]

    # Chunk 1 words (300s to 645s)
    chunk1_words = [
        {"word": "Overlap1_chunk1", "start": 310.1, "end": 310.6, "prob": 0.95},
        {"word": "Overlap2_chunk1", "start": 330.1, "end": 330.6, "prob": 0.95},
        {"word": "FutureWord", "start": 400.0, "end": 400.5, "prob": 0.99},
    ]

    # Midpoint of (300, 345) is 322.5
    reconciled = reconcile_transcript_words(
        existing_words=chunk0_words,
        new_words=chunk1_words,
        overlap_start=300.0,
        overlap_end=345.0,
    )

    words = [w["word"] for w in reconciled]
    # "Overlap1" (< 322.5) comes from chunk0
    assert "Overlap1" in words
    assert "Overlap1_chunk1" not in words

    # "Overlap2_chunk1" (>= 322.5) comes from chunk1
    assert "Overlap2_chunk1" in words
    assert "Overlap2" not in words

    # Non-overlapping words preserved
    assert "Hello" in words
    assert "FutureWord" in words
