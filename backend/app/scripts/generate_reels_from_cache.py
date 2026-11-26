import os
import uuid
import logging
from typing import List, Dict, Any
from app.database import SyncSessionLocal
from app.models.project import Project
from app.models.chunk import AnalysisChunk
from app.models.reel import Reel
from app.services.candidate import deduplicate_candidates, build_clip_subtitles
from app.services.gemini import analyze_chunk_with_gemini, generate_heuristic_candidates
from app.services.romanizer import romanize_words, romanize_text
from app.services.transcription import reconcile_transcript_words
from app.tasks.pipeline import render_reel_task
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_reels")

def populate_reels(project_id_str: str, target_count: int = 12):
    project_id = uuid.UUID(project_id_str)
    db = SyncSessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            print("Project not found.")
            return

        chunks = db.query(AnalysisChunk).filter(
            AnalysisChunk.project_id == project.id
        ).order_by(AnalysisChunk.chunk_index).all()

        print(f"Loaded {len(chunks)} chunks for {project.title}")

        # 1. Reconcile all transcript words across all chunks
        all_reconciled_words = []
        for idx, c in enumerate(chunks):
            if idx == 0:
                all_reconciled_words = c.transcript or []
            else:
                all_reconciled_words = reconcile_transcript_words(
                    existing_words=all_reconciled_words,
                    new_words=c.transcript or [],
                    overlap_start=float(c.start_time),
                    overlap_end=float(chunks[idx-1].end_time)
                )

        print(f"Reconciled {len(all_reconciled_words)} total words across entire timeline.")

        # 2. Existing reel ranges to avoid re-adding
        existing_reels = db.query(Reel).filter(Reel.project_id == project.id).all()
        existing_ranges = {(round(float(r.source_start), 1), round(float(r.source_end), 1)) for r in existing_reels}
        print(f"Found {len(existing_reels)} existing reels already in DB.")

        # 3. Collect candidates across all 69 chunks
        raw_candidates = []
        # Sample chunks across the 6-hour timeline
        step = max(1, len(chunks) // target_count)
        selected_chunk_indices = list(range(0, len(chunks), step))[:target_count + 4]

        for c_idx in selected_chunk_indices:
            c = chunks[c_idx]
            if not c.transcript or len(c.transcript) < 15:
                continue

            try:
                # Try Gemini first for catchy captions & AI scoring
                cands = analyze_chunk_with_gemini(
                    transcript_words=c.transcript,
                    scene_changes=c.scene_changes or [],
                    audio_peaks=c.audio_peaks or [],
                    chunk_start=float(c.start_time),
                    chunk_end=float(c.end_time),
                    max_retries=1
                )
            except Exception as e:
                logger.warning(f"Gemini call fallback for chunk {c_idx}: {e}")
                cands = []

            if not cands:
                cands = generate_heuristic_candidates(
                    transcript_words=c.transcript,
                    scene_changes=c.scene_changes or [],
                    audio_peaks=c.audio_peaks or [],
                    chunk_start=float(c.start_time),
                    chunk_end=float(c.end_time),
                )

            raw_candidates.extend(cands)

        unique_candidates = deduplicate_candidates(raw_candidates, iou_threshold=0.5)
        print(f"Discovered {len(unique_candidates)} unique candidates across selected timeline windows.")

        # 4. Create and save reels
        snapshot = project.settings_snapshot or {}
        reel_framing_mode = snapshot.get("framing_mode", project.framing_mode or "crop")
        reel_pan_x_offset = snapshot.get("pan_x_offset", project.pan_x_offset or 0.0)
        reel_font_size = snapshot.get("subtitle_font_size", project.subtitle_font_size or 54)
        reel_fc_crop = snapshot.get("split_facecam_crop", project.split_facecam_crop)
        reel_gp_crop = snapshot.get("split_gameplay_crop", project.split_gameplay_crop)
        reel_split_order = snapshot.get("split_order", project.split_order or "facecam_top")
        reel_split_ratio = snapshot.get("split_ratio", project.split_ratio or 0.35)
        reel_sub_pos = snapshot.get("subtitle_position", project.subtitle_position or "bottom")
        reel_sub_y = snapshot.get("subtitle_y_percent", project.subtitle_y_percent if project.subtitle_y_percent is not None else 0.82)
        reel_sub_col = snapshot.get("subtitle_color", project.subtitle_color or "#FFE500")
        reel_sub_font = snapshot.get("subtitle_font_family", project.subtitle_font_family or "Noto Sans")

        added_reels = []
        for cand in unique_candidates:
            if len(added_reels) >= target_count:
                break

            key_range = (round(float(cand["start_time"]), 1), round(float(cand["end_time"]), 1))
            if key_range in existing_ranges:
                continue

            subtitles = build_clip_subtitles(
                all_words=all_reconciled_words,
                clip_start=float(cand["start_time"]),
                clip_end=float(cand["end_time"]),
            )
            subtitles = romanize_words(subtitles)

            score = float(cand.get("overall_score", 75.0))
            is_borderline = score < settings.DEFAULT_MIN_SCORE
            top_caption_clean = romanize_text(cand["top_caption"])

            reel = Reel(
                project_id=project.id,
                title=top_caption_clean,
                reason=str(cand.get("reason", "Top stream highlight")),
                category=str(cand.get("category", "highlight")),
                source_start=float(cand["start_time"]),
                source_end=float(cand["end_time"]),
                clip_duration=float(cand["clip_duration"]),
                score=score,
                score_hook=float(cand.get("score_hook", 75.0)),
                score_payoff=float(cand.get("score_payoff", 75.0)),
                score_clarity=float(cand.get("score_clarity", 75.0)),
                score_entertainment=float(cand.get("score_entertainment", 75.0)),
                is_borderline=is_borderline,
                framing_mode=reel_framing_mode,
                pan_x_offset=float(reel_pan_x_offset),
                top_caption=top_caption_clean,
                subtitles_json=subtitles,
                subtitle_font_size=int(reel_font_size),
                subtitle_position=reel_sub_pos,
                subtitle_y_percent=float(reel_sub_y),
                subtitle_color=reel_sub_col,
                subtitle_font_family=reel_sub_font,
                split_facecam_crop=reel_fc_crop,
                split_gameplay_crop=reel_gp_crop,
                split_order=reel_split_order,
                split_ratio=float(reel_split_ratio),
                render_status="pending",
            )
            db.add(reel)
            db.flush()
            existing_ranges.add(key_range)
            added_reels.append(reel.id)
            print(f"Added Reel: {top_caption_clean} ({float(cand['start_time']):.1f}s - {float(cand['end_time']):.1f}s, score: {score})")

        db.commit()
        print(f"Successfully committed {len(added_reels)} new reels to the database!")

        # 5. Trigger rendering
        for r_id in added_reels:
            render_reel_task.delay(str(r_id))
        print("All reel render tasks queued to Celery worker.")

    finally:
        db.close()

if __name__ == "__main__":
    populate_reels("d81c1731-c89b-4c26-951b-14fe04ad2c24", target_count=12)
