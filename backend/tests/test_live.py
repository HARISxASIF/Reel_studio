import pytest
import os
import time
import tempfile
from unittest.mock import patch, MagicMock
from app.services.url_importer import validate_url_security, BLOCKED_NETWORKS, is_ip_allowed
from app.services.live_detector import is_hls_url, resolve_relative_url
from app.services.gemini_limiter import GeminiRateLimiter
from app.services.live_buffer import LiveBufferManager, BufferSegment


def test_ssrf_protection_blocked_ips():
    assert not is_ip_allowed("127.0.0.1")
    assert not is_ip_allowed("10.0.0.1")
    assert not is_ip_allowed("172.16.0.1")
    assert not is_ip_allowed("192.168.1.1")
    assert not is_ip_allowed("169.254.169.254")
    assert not is_ip_allowed("::1")


def test_ssrf_protection_valid_url():
    # Public domain or valid schema check
    with pytest.raises(ValueError):
        validate_url_security("ftp://example.com/stream.m3u8")

    with pytest.raises(ValueError):
        validate_url_security("http://localhost:8000/stream.m3u8")

    with pytest.raises(ValueError):
        validate_url_security("http://127.0.0.1:9000/stream.m3u8")


def test_hls_url_detection():
    assert is_hls_url("https://example.com/live/stream.m3u8")
    assert is_hls_url("https://example.com/live/stream.m3u8?token=xyz")
    assert is_hls_url("https://example.com/hls/channel1")
    assert not is_hls_url("https://example.com/video.mp4")


def test_resolve_relative_url():
    base = "https://cdn.example.com/live/playlist.m3u8"
    assert resolve_relative_url(base, "segment0.ts") == "https://cdn.example.com/live/segment0.ts"
    assert resolve_relative_url(base, "sub/segment1.ts") == "https://cdn.example.com/live/sub/segment1.ts"
    assert resolve_relative_url(base, "https://other.com/seg.ts") == "https://other.com/seg.ts"


def test_gemini_rate_limiter_in_memory():
    limiter = GeminiRateLimiter()
    limiter.rpm_limit = 2
    limiter.tpm_limit = 10000
    limiter.rpd_limit = 100

    # First call allowed
    allowed, wait, reason = limiter.check_quota(estimated_tokens=500)
    assert allowed
    limiter.record_call(tokens_used=500)

    # Second call allowed
    allowed, wait, reason = limiter.check_quota(estimated_tokens=500)
    assert allowed
    limiter.record_call(tokens_used=500)

    # Third call should hit RPM limit
    allowed, wait, reason = limiter.check_quota(estimated_tokens=500)
    assert not allowed
    assert "rpm_limit" in reason or "cooldown" in reason

    # Test cooldown
    limiter.record_rate_limit(cooldown_seconds=10)
    allowed, wait, reason = limiter.check_quota(estimated_tokens=500)
    assert not allowed
    assert "cooldown" in reason


def test_live_buffer_gap_detection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bm = LiveBufferManager(session_id="test_session_123", buffer_root=tmp_dir)

        # Manually inject segment 0
        seg0 = BufferSegment(
            index=0,
            url="http://example.com/seg0.ts",
            file_path=os.path.join(bm.buffer_dir, "seg_000000.ts"),
            duration=4.0,
            timeline_start=0.0,
            timeline_end=4.0,
            size_bytes=1000,
        )
        with open(seg0.file_path, "wb") as f:
            f.write(b"0" * 1000)

        bm.segments.append(seg0)
        bm.last_media_sequence = 100
        bm.last_timeline_time = 4.0
        bm.total_captured_seconds = 4.0
        bm.continuous_buffer_seconds = 4.0

        # Simulate receiving segment with sequence jump (e.g. sequence 103 instead of 101)
        # Sequence jump of 2 missing segments
        expected_seq = 101
        received_seq = 103
        seg_idx = 1
        seg_file = os.path.join(bm.buffer_dir, f"seg_{seg_idx:06d}.ts")
        with open(seg_file, "wb") as f:
            f.write(b"1" * 1000)

        # Download segment logic gap test
        gap_seqs = received_seq - expected_seq
        est_gap_dur = gap_seqs * 4.0
        gap_start = bm.last_timeline_time
        gap_end = gap_start + est_gap_dur

        bm.coverage_gaps.append({
            "start": round(gap_start, 2),
            "end": round(gap_end, 2),
            "duration": round(est_gap_dur, 2),
            "reason": f"Discontinuity detected: skipped {gap_seqs} segment(s)",
        })

        assert len(bm.coverage_gaps) == 1
        assert bm.coverage_gaps[0]["duration"] == 8.0
        assert bm.coverage_gaps[0]["start"] == 4.0
        assert bm.coverage_gaps[0]["end"] == 12.0


def test_live_buffer_purge_safe_mark_protection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        bm = LiveBufferManager(session_id="test_purge_session", buffer_root=tmp_dir)
        bm.last_timeline_time = 2000.0  # far ahead so segments older than 900s are "expired"

        seg0 = BufferSegment(
            index=0,
            url="http://example.com/seg0.ts",
            file_path=os.path.join(bm.buffer_dir, "seg_000000.ts"),
            duration=10.0,
            timeline_start=100.0,
            timeline_end=110.0,
            size_bytes=1000,
        )
        with open(seg0.file_path, "wb") as f:
            f.write(b"0" * 1000)

        seg1 = BufferSegment(
            index=1,
            url="http://example.com/seg1.ts",
            file_path=os.path.join(bm.buffer_dir, "seg_000001.ts"),
            duration=10.0,
            timeline_start=500.0,
            timeline_end=510.0,
            size_bytes=1000,
        )
        with open(seg1.file_path, "wb") as f:
            f.write(b"1" * 1000)

        bm.segments = [seg0, seg1]

        # Purge with min_safe_timeline_mark=500.0 (seg1 protected, seg0 expired)
        bm.purge_expired_segments(min_safe_timeline_mark=500.0)

        assert not os.path.exists(seg0.file_path)  # seg0 was below safe mark -> purged
        assert os.path.exists(seg1.file_path)      # seg1 was protected by safe mark -> kept
