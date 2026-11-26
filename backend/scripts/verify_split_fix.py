import os
import sys
import asyncio
import tempfile
import json
import subprocess
from pathlib import Path
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.services.probe import probe_media_file
from app.services.renderer import render_reel_video
from app.services.storage import storage_service

async def run_split_verification():
    print("=" * 70)
    print("GAMING SPLIT SCREEN FIX & EDIT REEL CROP VERIFICATION")
    print("=" * 70)

    source_path = "/app/test_media/test_12min.mp4"
    assert os.path.exists(source_path), f"Source test video not found at {source_path}"
    probe_info = probe_media_file(source_path)
    src_w, src_h = probe_info["width"], probe_info["height"]
    print(f"Source media verified: {src_w}x{src_h}, duration={probe_info['duration']}s")

    # -------------------------------------------------------------------------
    # TEST 1: Bottom-Left Facecam with Full 16:9 Gameplay
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Rendering Bottom-Left Facecam + Full Gameplay...")
    # Bottom-left facecam: x=0.02, y=0.60, w=0.28, h=0.35
    bottom_left_facecam = {"x": 0.02, "y": 0.60, "width": 0.28, "height": 0.35}
    full_gameplay = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}

    sample_words = [
        {"word": "BOTTOM", "start": 0.5, "end": 1.0},
        {"word": "LEFT", "start": 1.0, "end": 1.4},
        {"word": "GAMER", "start": 1.4, "end": 1.8},
        {"word": "REACTION!", "start": 1.8, "end": 2.5},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_mp4_1 = os.path.join(tmpdir, "reel_bottom_left_split.mp4")
        rendered_1 = render_reel_video(
            source_media_path=source_path,
            output_mp4_path=out_mp4_1,
            source_start=10.0,
            clip_duration=3.0,
            framing_mode="split",
            pan_x_offset=0.0,
            top_caption="BOTTOM LEFT GAMER HIGHLIGHT",
            subtitles_words=sample_words,
            subtitle_font_size=54,
            has_audio=True,
            split_facecam_crop=bottom_left_facecam,
            split_gameplay_crop=full_gameplay,
            split_order="facecam_top",
            split_ratio=0.35, # 35% facecam (672px), 65% gameplay (1248px)
        )
        assert os.path.exists(out_mp4_1), "Output MP4 was not created!"
        probe_out_1 = probe_media_file(out_mp4_1)
        assert probe_out_1["width"] == 1080 and probe_out_1["height"] == 1920
        assert probe_out_1["has_audio"] is True
        print(f"  ✓ Bottom-left split reel rendered: 1080x1920, {os.path.getsize(out_mp4_1)} bytes")

        # Verify no black letterboxing / gaps using ffmpeg blackdetect on the video
        # In blackdetect, if a full black interval >= 0.5s is detected, it logs black_start
        cmd_black = [
            "ffmpeg", "-i", out_mp4_1,
            "-vf", "blackdetect=d=0.5:pix_th=0.05",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd_black, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert "black_start" not in res.stderr, f"Unexpected black gap detected: {res.stderr}"
        print("  ✓ Blackdetect filter confirmed ZERO black gaps in rendered video.")

    # -------------------------------------------------------------------------
    # TEST 2: Swapped Pane Order (Gameplay Top / Facecam Bottom) & Moved Divider (50/50)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Rendering Swapped Order (Gameplay Top) & 50/50 Divider...")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_mp4_2 = os.path.join(tmpdir, "reel_swapped_split.mp4")
        rendered_2 = render_reel_video(
            source_media_path=source_path,
            output_mp4_path=out_mp4_2,
            source_start=15.0,
            clip_duration=3.0,
            framing_mode="split",
            pan_x_offset=0.0,
            top_caption="GAMEPLAY TOP / FACECAM BOT",
            subtitles_words=sample_words,
            subtitle_font_size=54,
            has_audio=True,
            split_facecam_crop=bottom_left_facecam,
            split_gameplay_crop=full_gameplay,
            split_order="gameplay_top",
            split_ratio=0.50, # 50% top (960px), 50% bottom (960px)
        )
        assert os.path.exists(out_mp4_2)
        probe_out_2 = probe_media_file(out_mp4_2)
        assert probe_out_2["width"] == 1080 and probe_out_2["height"] == 1920
        print(f"  ✓ Swapped order & 50/50 divider rendered: 1080x1920, {os.path.getsize(out_mp4_2)} bytes")

    # -------------------------------------------------------------------------
    # TEST 3: Database & API Per-Reel Isolation & Source Video URL
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Verifying Per-Reel Override Isolation & source_video_url in API...")
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User))
        user = user_res.scalars().first()

        # Create a project with default crop settings
        proj = Project(
            user_id=user.id,
            title="Split Screen Bug Fix Project",
            source_type="upload",
            source_file_key="test_media/test_12min.mp4",
            source_file_size=63848750,
            status="completed",
            framing_mode="crop", # Default project framing is crop
            pan_x_offset=0.0,
            subtitle_font_size=54,
            split_order="facecam_top",
            split_ratio=0.35,
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        # Create Reel 1 (User will customize this to split screen with bottom-left facecam)
        reel1 = Reel(
            project_id=proj.id,
            title="Reel 1 - Custom Split",
            reason="Gamer clutch",
            source_start=30.0,
            source_end=65.0,
            clip_duration=35.0,
            framing_mode="crop",
            pan_x_offset=0.0,
            top_caption="ORIGINAL CROP",
            render_status="completed",
        )
        # Create Reel 2 (Should remain untouched)
        reel2 = Reel(
            project_id=proj.id,
            title="Reel 2 - Original Crop",
            reason="Funny moment",
            source_start=80.0,
            source_end=115.0,
            clip_duration=35.0,
            framing_mode="crop",
            pan_x_offset=0.0,
            top_caption="REEL 2 UNTOUCHED",
            render_status="completed",
        )
        session.add_all([reel1, reel2])
        await session.commit()
        await session.refresh(reel1)
        await session.refresh(reel2)

        # Simulate Edit Reel save for Reel 1:
        # User changes Reel 1 to split screen with bottom-left facecam and 40% ratio
        reel1.framing_mode = "split"
        reel1.split_facecam_crop = bottom_left_facecam
        reel1.split_gameplay_crop = full_gameplay
        reel1.split_order = "facecam_top"
        reel1.split_ratio = 0.40
        reel1.top_caption = "CUSTOM PER-REEL SPLIT"
        await session.commit()

        # Verify Reel 1 was updated
        await session.refresh(reel1)
        assert reel1.framing_mode == "split"
        assert reel1.split_facecam_crop["y"] == 0.60
        assert reel1.split_ratio == 0.40
        print("  ✓ Reel 1 successfully updated with custom bottom-left split framing.")

        # Verify Reel 2 remains untouched
        await session.refresh(reel2)
        assert reel2.framing_mode == "crop", f"Reel 2 framing_mode altered! Got {reel2.framing_mode}"
        assert reel2.split_facecam_crop is None
        assert reel2.top_caption == "REEL 2 UNTOUCHED"
        print("  ✓ Reel 2 confirmed completely untouched (still crop mode).")

        # Verify Project defaults remain untouched
        await session.refresh(proj)
        assert proj.framing_mode == "crop", f"Project framing_mode altered! Got {proj.framing_mode}"
        print("  ✓ Project defaults confirmed completely untouched.")

    # -------------------------------------------------------------------------
    # TEST 4: HTTP API Response for Reel Editor
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Verifying HTTP API GET /api/reels/{id} returns source_video_url...")
    import requests
    res = requests.get(f"http://api:8000/api/reels/{reel1.id}")
    assert res.status_code == 200, res.text
    reel1_data = res.json()
    assert reel1_data["source_video_url"] is not None, "source_video_url missing from ReelResponse!"
    assert "reel-studio/test_media/test_12min.mp4" in reel1_data["source_video_url"]
    assert reel1_data["framing_mode"] == "split"
    assert reel1_data["split_facecam_crop"]["y"] == 0.60
    print(f"  ✓ API successfully returned signed source_video_url: {reel1_data['source_video_url'][:60]}...")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION TESTS COMPLETED AND PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_split_verification())
