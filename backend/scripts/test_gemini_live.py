import os
import sys
from app.services.gemini import analyze_chunk_with_gemini, is_gemini_configured
from app.config import settings

def test_live_gemini():
    print("=" * 60)
    print("TESTING LIVE GEMINI INTEGRATION")
    print("=" * 60)
    print(f"Configured: {is_gemini_configured()}")
    print(f"Model: {settings.GEMINI_MODEL}")
    
    sample_words = [
        {"word": "Welcome", "start": 5.0, "end": 5.5, "prob": 0.99},
        {"word": "everyone", "start": 5.5, "end": 6.0, "prob": 0.99},
        {"word": "to", "start": 6.0, "end": 6.2, "prob": 0.99},
        {"word": "the", "start": 6.2, "end": 6.4, "prob": 0.99},
        {"word": "championship!", "start": 6.4, "end": 7.5, "prob": 0.99},
        {"word": "Today", "start": 8.0, "end": 8.5, "prob": 0.99},
        {"word": "we", "start": 8.5, "end": 8.7, "prob": 0.99},
        {"word": "are", "start": 8.7, "end": 8.9, "prob": 0.99},
        {"word": "breaking", "start": 8.9, "end": 9.5, "prob": 0.99},
        {"word": "the", "start": 9.5, "end": 9.7, "prob": 0.99},
        {"word": "world", "start": 9.7, "end": 10.1, "prob": 0.99},
        {"word": "record!", "start": 10.1, "end": 11.0, "prob": 0.99},
        {"word": "Watch", "start": 25.0, "end": 25.5, "prob": 0.99},
        {"word": "until", "start": 25.5, "end": 26.0, "prob": 0.99},
        {"word": "the", "start": 26.0, "end": 26.2, "prob": 0.99},
        {"word": "very", "start": 26.2, "end": 26.8, "prob": 0.99},
        {"word": "end", "start": 26.8, "end": 27.5, "prob": 0.99},
        {"word": "because", "start": 32.0, "end": 32.6, "prob": 0.99},
        {"word": "the", "start": 32.6, "end": 32.8, "prob": 0.99},
        {"word": "final", "start": 32.8, "end": 33.5, "prob": 0.99},
        {"word": "move", "start": 33.5, "end": 34.0, "prob": 0.99},
        {"word": "is", "start": 34.0, "end": 34.2, "prob": 0.99},
        {"word": "absolutely", "start": 34.2, "end": 35.0, "prob": 0.99},
        {"word": "insane!", "start": 35.0, "end": 36.5, "prob": 0.99},
        {"word": "Boom,", "start": 37.0, "end": 37.8, "prob": 0.99},
        {"word": "we", "start": 37.8, "end": 38.0, "prob": 0.99},
        {"word": "did", "start": 38.0, "end": 38.5, "prob": 0.99},
        {"word": "it!", "start": 38.5, "end": 39.5, "prob": 0.99},
    ]

    scene_changes = [5.0, 15.0, 30.0]
    audio_peaks = [{"time": 10.5, "energy": 0.92}]

    print("\nCalling analyze_chunk_with_gemini()...")
    cands = analyze_chunk_with_gemini(
        transcript_words=sample_words,
        scene_changes=scene_changes,
        audio_peaks=audio_peaks,
        chunk_start=0.0,
        chunk_end=45.0,
    )

    print(f"\nCandidates returned: {len(cands)}")
    assert len(cands) > 0, "No candidates returned!"

    for i, c in enumerate(cands, 1):
        print(f"\n[Candidate {i}]")
        print(f"  Title: {c.get('top_caption')}")
        print(f"  Category: {c.get('category')}")
        print(f"  Duration: {c.get('clip_duration')}s ({c.get('start_time')}s -> {c.get('end_time')}s)")
        print(f"  Score: {c.get('overall_score')} (Hook: {c.get('score_hook')}, Payoff: {c.get('score_payoff')})")
        print(f"  Reason: {c.get('reason')}")
        print(f"  Source: {c.get('source')}")
        assert 30.0 <= c.get('clip_duration') <= 60.5, f"Invalid duration {c.get('clip_duration')}"
        assert c.get('source') == 'gemini', f"Expected source to be 'gemini', got '{c.get('source')}'"

    print("\n" + "=" * 60)
    print("LIVE GEMINI TEST PASSED WITH FLYING COLORS!")
    print("=" * 60)

if __name__ == "__main__":
    test_live_gemini()
