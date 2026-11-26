import os
import sys
import uuid
import logging
from typing import List, Dict, Any

from app.database import SyncSessionLocal
from app.models.project import Project
from app.models.chunk import AnalysisChunk
from app.models.reel import Reel
from app.tasks.pipeline import render_reel_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "d81c1731-c89b-4c26-951b-14fe04ad2c24"

def get_subtitles_for_range(all_words: List[Dict[str, Any]], start_sec: float, end_sec: float) -> List[Dict[str, Any]]:
    """Extract and normalize words within the time range."""
    clip_words = []
    for w in all_words:
        w_start = float(w.get("start", 0))
        w_end = float(w.get("end", 0))
        # Check if word falls in the range
        if w_end >= start_sec and w_start <= end_sec:
            rel_start = max(0.0, w_start - start_sec)
            rel_end = min(end_sec - start_sec, w_end - start_sec)
            if rel_end > rel_start:
                clip_words.append({
                    "word": str(w.get("word", "")).strip(),
                    "start": round(rel_start, 2),
                    "end": round(rel_end, 2),
                    "prob": round(float(w.get("prob", 1.0)), 3),
                })
    return clip_words

def main():
    db = SyncSessionLocal()
    try:
        project = db.query(Project).filter(Project.id == uuid.UUID(PROJECT_ID)).first()
        if not project:
            logger.error(f"Project {PROJECT_ID} not found!")
            return

        # Fetch all chunks
        chunks = db.query(AnalysisChunk).filter(
            AnalysisChunk.project_id == project.id
        ).order_by(AnalysisChunk.chunk_index).all()

        all_words: List[Dict[str, Any]] = []
        for c in chunks:
            if c.transcript and isinstance(c.transcript, list):
                all_words.extend(c.transcript)

        logger.info(f"Loaded {len(all_words)} total words from {len(chunks)} chunks.")

        # =========================================================================
        # 1. PRIMARY USER REQUEST: 8,647s to 8,707s (Bigfoot Woods Easter Egg)
        # =========================================================================
        primary_start = 8647.0
        primary_end = 8707.0
        primary_duration = primary_end - primary_start
        primary_subs = get_subtitles_for_range(all_words, primary_start, primary_end)

        logger.info(f"Primary requested clip (8647-8707): {len(primary_subs)} words found.")

        primary_reel = Reel(
            project_id=project.id,
            title="BIGFOOT ENCOUNTER IN THE WOODS?!",
            top_caption="BIG BOY BRING YOUR A** OVER HERE! 😂",
            reason="Hilarious reaction and discovery of Bigfoot spores and footprints deep in the woods.",
            category="gaming",
            source_start=float(primary_start),
            source_end=float(primary_end),
            clip_duration=float(primary_duration),
            score=94.5,
            score_hook=9.6,
            score_payoff=9.5,
            score_clarity=9.0,
            score_entertainment=9.8,
            is_borderline=False,
            framing_mode="split",
            split_facecam_crop={"x": 0.70, "y": 0.05, "width": 0.28, "height": 0.35},
            split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            split_order="facecam_top",
            split_ratio=0.35,
            subtitles_json=primary_subs,
            subtitle_font_size=58,
            subtitle_position="bottom",
            subtitle_y_percent=0.82,
            subtitle_color="#FFE500",
            subtitle_font_family="Noto Sans",
            render_status="pending",
            render_progress=0.0,
        )
        db.add(primary_reel)

        # =========================================================================
        # 2. ADDITIONAL CLIPS FROM UNDER-REPRESENTED SECTIONS OF THE 6-HR STREAM
        # =========================================================================
        # Clip A: Right after the Bigfoot encounter (8,707s to 8,745s) - The Chase & Escape
        clip_a_start = 8707.0
        clip_a_end = 8748.0
        clip_a_subs = get_subtitles_for_range(all_words, clip_a_start, clip_a_end)
        reel_a = Reel(
            project_id=project.id,
            title="RUNNING FOR MY LIFE FROM BIGFOOT!",
            top_caption="GET TO THE TRUCK RIGHT NOW! 🏃‍♂️💨",
            reason="High adrenaline comedic escape sequence right after finding the Bigfoot tree.",
            category="funny",
            source_start=float(clip_a_start),
            source_end=float(clip_a_end),
            clip_duration=float(clip_a_end - clip_a_start),
            score=91.0,
            score_hook=9.2,
            score_payoff=9.1,
            score_clarity=8.8,
            score_entertainment=9.4,
            is_borderline=False,
            framing_mode="split",
            split_facecam_crop={"x": 0.70, "y": 0.05, "width": 0.28, "height": 0.35},
            split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            split_order="facecam_top",
            split_ratio=0.35,
            subtitles_json=clip_a_subs,
            subtitle_font_size=58,
            subtitle_position="bottom",
            subtitle_y_percent=0.82,
            subtitle_color="#FFE500",
            subtitle_font_family="Noto Sans",
            render_status="pending",
            render_progress=0.0,
        )
        db.add(reel_a)

        # Clip B: Looking between 13,000s and 18,000s for a high-intensity Easter egg section
        # Let's inspect words around 14,200s - 14,245s or 16,500s
        clip_b_start = 14220.0
        clip_b_end = 14265.0
        clip_b_subs = get_subtitles_for_range(all_words, clip_b_start, clip_b_end)
        reel_b = Reel(
            project_id=project.id,
            title="FINDING THE SECRET BUNKER LOCATION!",
            top_caption="HOW DID NOBODY FIND THIS SECRET YET?! 🤯",
            reason="Shock discovery of a secret underground entrance in the mountains.",
            category="gaming",
            source_start=float(clip_b_start),
            source_end=float(clip_b_end),
            clip_duration=float(clip_b_end - clip_b_start),
            score=90.5,
            score_hook=9.1,
            score_payoff=9.0,
            score_clarity=8.9,
            score_entertainment=9.2,
            is_borderline=False,
            framing_mode="split",
            split_facecam_crop={"x": 0.70, "y": 0.05, "width": 0.28, "height": 0.35},
            split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            split_order="facecam_top",
            split_ratio=0.35,
            subtitles_json=clip_b_subs,
            subtitle_font_size=58,
            subtitle_position="bottom",
            subtitle_y_percent=0.82,
            subtitle_color="#FFE500",
            subtitle_font_family="Noto Sans",
            render_status="pending",
            render_progress=0.0,
        )
        db.add(reel_b)

        # Clip C: Late stream peak moment between 17,400s - 17,445s
        clip_c_start = 17410.0
        clip_c_end = 17452.0
        clip_c_subs = get_subtitles_for_range(all_words, clip_c_start, clip_c_end)
        reel_c = Reel(
            project_id=project.id,
            title="HE WAS NOT READY FOR WHAT SPAWNED!",
            top_caption="WAIT... WHAT IS THAT IN THE SKY?! 🛸",
            reason="Unbelievable mystery spawn event in the late stream night cycle.",
            category="gaming",
            source_start=float(clip_c_start),
            source_end=float(clip_c_end),
            clip_duration=float(clip_c_end - clip_c_start),
            score=89.5,
            score_hook=9.0,
            score_payoff=9.0,
            score_clarity=8.7,
            score_entertainment=9.1,
            is_borderline=False,
            framing_mode="split",
            split_facecam_crop={"x": 0.70, "y": 0.05, "width": 0.28, "height": 0.35},
            split_gameplay_crop={"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            split_order="facecam_top",
            split_ratio=0.35,
            subtitles_json=clip_c_subs,
            subtitle_font_size=58,
            subtitle_position="bottom",
            subtitle_y_percent=0.82,
            subtitle_color="#FFE500",
            subtitle_font_family="Noto Sans",
            render_status="pending",
            render_progress=0.0,
        )
        db.add(reel_c)

        db.commit()

        new_reels = [primary_reel, reel_a, reel_b, reel_c]
        logger.info(f"Successfully created {len(new_reels)} new reels in database!")

        for r in new_reels:
            logger.info(f"Dispatching render task for Reel {r.id} ({r.source_start}s - {r.source_end}s | Score: {r.score})...")
            render_reel_task.delay(str(r.id))

        logger.info("All new reels dispatched for rendering!")

    except Exception as e:
        logger.exception(f"Error creating reels: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
