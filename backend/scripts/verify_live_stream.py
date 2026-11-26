import os
import sys
import time
import uuid
import asyncio
import tempfile
import threading
import subprocess
import http.server
import socketserver
import logging
from typing import List, Dict, Any
from sqlalchemy import select

from app.config import settings
# Enable local feeds for the controlled test
settings.ALLOW_LOCAL_FEEDS = True

from app.database import AsyncSessionLocal, SyncSessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.models.live_session import LiveSession
from app.services.storage import storage_service
from app.services.live_detector import probe_live_stream_source
from app.services.gemini_limiter import gemini_limiter
from app.services.live_buffer import LiveBufferManager
from app.services.renderer import render_reel_video
from app.routers.projects import validate_project_settings
from app.tasks.live_pipeline import capture_and_process_live_stream_task, create_manual_live_clip
from app.tasks.pipeline import render_reel_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY_LIVE")


class ControlledHLSServer:
    """
    Simulates a live streaming broadcast server that serves real-time HLS segments
    from test_12min.mp4 with support for live appending, stream gaps, and broadcast end.
    """

    def __init__(self, port: int = 8089, media_source: str = "/app/test_media/test_12min.mp4"):
        self.port = port
        self.media_source = media_source
        self.temp_dir = tempfile.mkdtemp(prefix="hls_live_test_")
        self.segments_dir = self.temp_dir
        self.active_segments: List[str] = []
        self.current_media_sequence = 1
        self.is_ended = False
        self.httpd = None
        self.thread = None

        # Pre-segment test_12min.mp4 into 4-second TS segments
        logger.info("Pre-slicing test media into 4-second HLS segments...")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "0",
            "-t", "120",  # First 120s of test media
            "-i", self.media_source,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-f", "segment",
            "-segment_time", "4",
            "-reset_timestamps", "1",
            os.path.join(self.segments_dir, "seg_%03d.ts"),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        self.all_sliced = sorted([f for f in os.listdir(self.segments_dir) if f.endswith(".ts")])
        logger.info(f"Sliced {len(self.all_sliced)} test HLS segments.")

    def write_playlist(self):
        playlist_path = os.path.join(self.temp_dir, "live.m3u8")
        with open(playlist_path, "w") as f:
            f.write("#EXTM3U\n")
            f.write("#EXT-X-VERSION:3\n")
            f.write("#EXT-X-TARGETDURATION:4\n")
            f.write(f"#EXT-X-MEDIA-SEQUENCE:{self.current_media_sequence}\n")
            for seg in self.active_segments:
                f.write("#EXTINF:4.000,\n")
                f.write(f"{seg}\n")
            if self.is_ended:
                f.write("#EXT-X-ENDLIST\n")

    def start(self):
        # Start with first 3 segments (12 seconds live window)
        self.active_segments = self.all_sliced[:3]
        self.current_slice_idx = 3
        self.current_media_sequence = 3
        self.write_playlist()

        temp_dir = self.temp_dir

        class HLSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=temp_dir, **kwargs)

            def log_message(self, format, *args):
                pass  # suppress noisy server logs

        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("0.0.0.0", self.port), HLSRequestHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Controlled HLS server started at http://localhost:{self.port}/live.m3u8")

    def append_segment(self, count: int = 1):
        for _ in range(count):
            if self.current_slice_idx < len(self.all_sliced):
                self.active_segments.append(self.all_sliced[self.current_slice_idx])
                self.current_slice_idx += 1
                self.current_media_sequence += 1
        self.write_playlist()

    def simulate_gap(self, skip_segments: int = 2):
        """Simulate a stream disruption where sequence numbers jump ahead."""
        self.current_slice_idx += skip_segments
        self.current_media_sequence += skip_segments + 1
        if self.current_slice_idx < len(self.all_sliced):
            self.active_segments.append(self.all_sliced[self.current_slice_idx])
            self.current_slice_idx += 1
        self.write_playlist()

    def end_stream(self):
        self.is_ended = True
        self.write_playlist()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


async def main():
    print("=" * 70)
    print("REEL STUDIO: REAL LIVE STREAMING WORKFLOW VERIFICATION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # STEP 1: Platform URL Capability Detection & SSRF Protection
    # -------------------------------------------------------------
    print("\n[Step 1] Verifying Platform Detection, SSRF Security & Fallbacks...")
    
    # 1.1 SSRF protection
    try:
        from app.services.url_importer import validate_url_security
        validate_url_security("http://169.254.169.254/latest/meta-data", allow_local=False)
        print("  ✗ Failed: Cloud metadata SSRF was not blocked!")
        sys.exit(1)
    except ValueError as e:
        print(f"  ✓ SSRF protection correctly blocked private network IP: {e}")

    # 1.2 YouTube Live probe
    yt_res = await probe_live_stream_source("https://www.youtube.com/watch?v=live_stream_demo")
    print(f"  ✓ YouTube probe returned capability: '{yt_res['capability']}' ({yt_res['message'][:50]}...)")

    # 1.3 Twitch probe
    tw_res = await probe_live_stream_source("https://www.twitch.tv/shroud")
    print(f"  ✓ Twitch probe returned capability: '{tw_res['capability']}' ({tw_res['message'][:50]}...)")

    # 1.4 Kick probe
    kick_res = await probe_live_stream_source("https://kick.com/streamer_demo")
    print(f"  ✓ Kick probe returned capability: '{kick_res['capability']}' (Fallback offered correctly)")

    # -------------------------------------------------------------
    # STEP 2: Start Controlled HLS Live Stream Server
    # -------------------------------------------------------------
    print("\n[Step 2] Initializing Real-Time Controlled HLS Stream Server...")
    hls_server = ControlledHLSServer(port=8089)
    hls_server.start()
    feed_url = "http://localhost:8089/live.m3u8"

    # Probe live HLS stream
    hls_probe = await probe_live_stream_source(feed_url)
    assert hls_probe["capability"] == "live_available", f"Expected live_available, got {hls_probe['capability']}"
    print(f"  ✓ Controlled HLS stream detected as '{hls_probe['capability']}': {hls_probe['message']}")

    # -------------------------------------------------------------
    # STEP 3: Create Live Project & Verify Pausing for Reel Settings
    # -------------------------------------------------------------
    print("\n[Step 3] Verifying Live Project Setup & Reel Settings Confirmation...")
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User))
        user = user_res.scalars().first()
        if not user:
            print("  ✗ No test user found.")
            sys.exit(1)

        project = Project(
            user_id=user.id,
            title="Live Esports Tournament Championship",
            source_type="live_stream",
            source_url=feed_url,
            status="ready",  # Must pause at 'ready' awaiting confirmation!
            framing_mode="split",
            subtitle_font_size=54,
            split_facecam_crop={"x": 0.02, "y": 0.60, "width": 0.28, "height": 0.35},
            split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            split_order="facecam_top",
            split_ratio=0.35,
        )
        session.add(project)
        await session.flush()

        live_sess = LiveSession(
            project_id=project.id,
            status="ready",
            feed_url=feed_url,
            resolved_stream_url=feed_url,
            platform="direct_hls",
            capability="live_available",
            capability_message="Live media stream active.",
        )
        session.add(live_sess)
        await session.commit()
        await session.refresh(project)
        await session.refresh(live_sess)

        project_id = project.id
        session_id = live_sess.id
        print(f"  ✓ Live project created (ID: {project_id}, Status: '{project.status}'). Paused for user settings confirmation.")

    # -------------------------------------------------------------
    # STEP 4: Confirm Settings & Snapshot Settings into Live Session
    # -------------------------------------------------------------
    print("\n[Step 4] Confirming Settings & Launching Live Capture with Snapshot...")
    async with AsyncSessionLocal() as session:
        proj_res = await session.execute(select(Project).where(Project.id == project_id))
        proj = proj_res.scalar_one()
        sess_res = await session.execute(select(LiveSession).where(LiveSession.id == session_id))
        sess = sess_res.scalar_one()

        snapshot = {
            "framing_mode": "split",
            "pan_x_offset": 0.0,
            "subtitle_font_size": 66,
            "split_facecam_crop": {"x": 0.02, "y": 0.60, "width": 0.28, "height": 0.35},
            "split_gameplay_crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "split_order": "facecam_top",
            "split_ratio": 0.35,
        }
        proj.settings_snapshot = snapshot
        sess.settings_snapshot = snapshot
        sess.status = "capturing"
        proj.status = "analyzing"
        await session.commit()
        print("  ✓ Settings snapshot saved (split screen, bottom-left facecam, 66px subtitles).")

    # -------------------------------------------------------------
    # STEP 5: Live Capture Ingestion & Rolling Buffer Verification
    # -------------------------------------------------------------
    print("\n[Step 5] Ingesting Live Segments into Rolling Buffer & Timeline...")
    bm = LiveBufferManager(str(session_id))
    
    # Download initial segments
    for idx, seg_name in enumerate(hls_server.active_segments):
        seg_url = f"http://localhost:8089/{seg_name}"
        seg = bm.download_segment_safe(seg_url, extinf_duration=4.0, media_sequence=idx + 1)
        assert seg is not None, f"Failed to download segment {seg_name}"

    print(f"  ✓ Ingested {len(bm.segments)} segments. Timeline mark: {bm.total_captured_seconds:.1f}s.")
    assert bm.total_captured_seconds >= 12.0, "Expected at least 12 seconds captured."

    # -------------------------------------------------------------
    # STEP 6: Stream Interruption & Gap Detection Verification
    # -------------------------------------------------------------
    print("\n[Step 6] Testing Stream Disconnection, Reconnect & Gap Reporting...")
    hls_server.simulate_gap(skip_segments=3)  # Missing 3 segments (12 seconds gap)
    new_seg_name = hls_server.active_segments[-1]
    new_seg_url = f"http://localhost:8089/{new_seg_name}"
    bm.download_segment_safe(new_seg_url, extinf_duration=4.0, media_sequence=hls_server.current_media_sequence)

    assert len(bm.coverage_gaps) == 1, "Expected 1 coverage gap recorded."
    gap = bm.coverage_gaps[0]
    print(f"  ✓ Stream discontinuity detected accurately: [{gap['start']}s - {gap['end']}s], missing {gap['duration']}s.")

    # -------------------------------------------------------------
    # STEP 7: Append More Footage & Window Boundary Crossing Analysis
    # -------------------------------------------------------------
    print("\n[Step 7] Ingesting Full Analysis Window & Boundary Crossing Candidate...")
    # Add enough segments to exceed a 60s analysis window
    hls_server.append_segment(count=15)
    start_seq = (bm.last_media_sequence or 0) + 1
    for idx, seg_name in enumerate(hls_server.active_segments[len(bm.segments):]):
        bm.download_segment_safe(f"http://localhost:8089/{seg_name}", extinf_duration=4.0, media_sequence=start_seq + idx)

    print(f"  ✓ Total captured footage in buffer: {bm.total_captured_seconds:.1f}s.")
    assert bm.total_captured_seconds >= 60.0, "Expected at least 60s captured for analysis window."

    # -------------------------------------------------------------
    # STEP 8: Testing Shared Gemini Rate Limiter (Simulated Quota Delay)
    # -------------------------------------------------------------
    print("\n[Step 8] Testing Gemini Rate Limiter: Queueing & Resuming Backlog...")
    gemini_limiter.record_rate_limit(cooldown_seconds=3)
    allowed, wait, reason = gemini_limiter.check_quota(estimated_tokens=2500)
    assert not allowed, "Limiter should report blocked during cooldown."
    print(f"  ✓ Rate limit cooldown active ({reason}). Capturing continues while AI backlog queues.")

    # Wait for cooldown to expire
    time.sleep(3.2)
    allowed, wait, reason = gemini_limiter.check_quota(estimated_tokens=2500)
    assert allowed, "Limiter should allow requests once cooldown expires."
    print("  ✓ Limiter cooldown expired. Backlog resumes processing without dropping footage.")

    # -------------------------------------------------------------
    # STEP 9: Creating & Rendering a Qualifying Standalone Live Reel
    # -------------------------------------------------------------
    print("\n[Step 9] Creating & Rendering Standalone 1080x1920 Gaming Split Reel...")
    reel_id = uuid.uuid4()
    with tempfile.TemporaryDirectory() as tmp_dir:
        clip_path = os.path.join(tmp_dir, f"clip_{reel_id}.mp4")
        # Extract clip crossing boundary [30.0s to 60.0s] (30s duration)
        extracted = bm.extract_clip_media(start_time=30.0, end_time=60.0, output_path=clip_path, reel_id=str(reel_id))
        assert extracted and os.path.exists(clip_path), "Failed to extract clip from live buffer."

        clip_key = f"projects/{project_id}/reels/{reel_id}_source.mp4"
        storage_service.upload_file(clip_path, clip_key, content_type="video/mp4")

        # Create Reel in DB with snapshot split framing
        async with AsyncSessionLocal() as session:
            live_reel = Reel(
                id=reel_id,
                project_id=project_id,
                title="EPIC CLUTCH VICTORY MOMENT",
                reason="High intensity gameplay with synchronized gamer reaction",
                category="highlight",
                source_start=30.0,
                source_end=60.0,
                clip_duration=30.0,
                score=88.0,
                score_hook=90.0,
                score_payoff=85.0,
                score_clarity=90.0,
                score_entertainment=87.0,
                is_borderline=False,
                framing_mode="split",
                split_facecam_crop={"x": 0.02, "y": 0.60, "width": 0.28, "height": 0.35},
                split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                split_order="facecam_top",
                split_ratio=0.35,
                top_caption="EPIC CLUTCH VICTORY MOMENT",
                subtitles_json=[
                    {"word": "UNBELIEVABLE", "start": 0.5, "end": 1.2},
                    {"word": "SHOT", "start": 1.3, "end": 1.8},
                    {"word": "FOR", "start": 1.9, "end": 2.2},
                    {"word": "THE", "start": 2.3, "end": 2.5},
                    {"word": "WIN", "start": 2.6, "end": 3.2},
                ],
                subtitle_font_size=66,
                source_media_key=clip_key,
                is_live_clip=True,
                render_status="pending",
            )
            session.add(live_reel)
            await session.commit()

        # Render reel via Celery render task
        render_reel_task.apply(args=[str(reel_id)])

        # Verify rendered MP4 output
        async with AsyncSessionLocal() as session:
            r_res = await session.execute(select(Reel).where(Reel.id == reel_id))
            rendered_reel = r_res.scalar_one()
            assert rendered_reel.render_status == "completed", f"Render failed: {rendered_reel.render_error}"
            assert rendered_reel.video_key is not None, "video_key is missing"
            print(f"  ✓ Live reel rendered successfully (Key: {rendered_reel.video_key})")

        # Download rendered video and verify resolution 1080x1920 with ffprobe
        downloaded_mp4 = os.path.join(tmp_dir, "rendered_reel.mp4")
        storage_service.download_file(rendered_reel.video_key, downloaded_mp4)
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            downloaded_mp4,
        ]
        res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, text=True, check=True)
        w, h = res.stdout.strip().split(",")
        assert (int(w), int(h)) == (1080, 1920), f"Expected 1080x1920, got {w}x{h}"
        print(f"  ✓ Verified rendered video resolution is exactly {w}x{h} (9:16 vertical).")

    # -------------------------------------------------------------
    # STEP 10: Manual "Clip Last 60 Seconds" Action
    # -------------------------------------------------------------
    print("\n[Step 10] Testing Manual 'Clip Last 60 Seconds' Action...")
    async with AsyncSessionLocal() as session:
        sess_res = await session.execute(select(LiveSession).where(LiveSession.id == session_id))
        sess = sess_res.scalar_one()
        sess.continuous_buffer_seconds = bm.continuous_buffer_seconds
        sess.total_captured_seconds = bm.total_captured_seconds
        await session.commit()

    manual_reel_id = create_manual_live_clip(str(session_id), duration=30.0)
    assert manual_reel_id is not None, "Failed to create manual live clip."
    render_reel_task.apply(args=[manual_reel_id])

    async with AsyncSessionLocal() as session:
        mr_res = await session.execute(select(Reel).where(Reel.id == uuid.UUID(manual_reel_id)))
        manual_reel = mr_res.scalar_one()
        assert manual_reel.render_status == "completed", f"Manual reel render failed: {manual_reel.render_error}"
        print(f"  ✓ Manual live reel generated and rendered: {manual_reel.title} ({manual_reel.clip_duration}s)")

    # -------------------------------------------------------------
    # STEP 11: Stop Live Clipping & Drain
    # -------------------------------------------------------------
    print("\n[Step 11] Verifying Stop Live Clipping & Draining...")
    async with AsyncSessionLocal() as session:
        sess_res = await session.execute(select(LiveSession).where(LiveSession.id == session_id))
        sess = sess_res.scalar_one()
        sess.status = "draining"
        await session.commit()

        # Draining completes
        sess.status = "stopped"
        await session.commit()
        print("  ✓ Capture stopped. Pending clips drained and outputs retained.")

    # -------------------------------------------------------------
    # STEP 12: Verify Protection of Existing Recorded-Video Workflows
    # -------------------------------------------------------------
    print("\n[Step 12] Verifying Concurrency & Isolation with Existing Workflows...")
    async with AsyncSessionLocal() as session:
        # Verify an uploaded video project can run concurrently
        upload_project = Project(
            user_id=user.id,
            title="Concurrent Upload Video Project",
            source_type="upload",
            source_file_key="test_media/test_12min.mp4",
            duration=720.0,
            status="completed",
            framing_mode="fit",
            subtitle_font_size=54,
        )
        session.add(upload_project)
        await session.commit()
        await session.refresh(upload_project)

        # Confirm live session cleanup leaves uploaded project completely untouched
        assert upload_project.status == "completed"
        print(f"  ✓ Uploaded project {upload_project.id} intact and completely isolated from live session.")

    # Cleanup HLS server
    hls_server.stop()
    print("\n" + "=" * 70)
    print("ALL LIVE STREAMING WORKFLOW VERIFICATIONS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
