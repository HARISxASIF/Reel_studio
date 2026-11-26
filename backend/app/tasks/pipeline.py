import os
import time
import uuid
import tempfile
import logging
from typing import List, Dict, Any
from app.tasks.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models.project import Project
from app.models.chunk import AnalysisChunk
from app.models.reel import Reel
from app.models.bulk_export import BulkExport
from app.services.storage import storage_service
from app.services.probe import probe_media_file
from app.services.transcription import transcribe_media_segment, reconcile_transcript_words
from app.services.visual_audio import detect_scene_changes, detect_audio_peaks, extract_keyframe
from app.services.gemini import analyze_chunk_with_gemini
from app.services.candidate import deduplicate_candidates, build_clip_subtitles
from app.services.renderer import render_reel_video
from app.services.zip_export import create_reels_zip_archive
from app.services.url_importer import download_remote_media_to_minio
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_url_import(self, project_id_str: str, url: str):
    """
    Background task to import media from remote URL (YouTube, Twitch, Kick, direct),
    verify with FFprobe, and mark project as 'ready' for user Reel Settings.
    """
    project_id = uuid.UUID(project_id_str)
    db = SyncSessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        project.status = "importing"
        project.error_message = None
        db.commit()

        file_key = f"projects/{project.id}/source.mp4"
        with tempfile.TemporaryDirectory() as tmp_dir:
            last_err = None
            local_path = None
            file_size = 0
            probe_data = None

            for attempt in range(2):
                try:
                    local_path, file_size = download_remote_media_to_minio(url, file_key, tmp_dir)
                    probe_data = probe_media_file(local_path)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"URL import attempt {attempt + 1} failed for {url}: {e}")
                    time.sleep(2.0)

            if last_err is not None or not probe_data:
                logger.error(f"URL import failed for {url}: {last_err}")
                project.status = "failed"
                project.error_message = f"Media import failed: {str(last_err)}. You can retry or upload the original file directly."
                db.commit()
                return

        project.source_file_key = file_key
        project.source_file_size = file_size
        project.duration = probe_data["duration"]
        project.probe_data = probe_data
        project.status = "ready"
        db.commit()

    except Exception as exc:
        logger.error(f"Unhandled error in process_url_import: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "failed"
            project.error_message = f"Import error: {str(exc)}"
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def probe_and_prepare_source(self, project_id_str: str):
    """
    Background task to probe uploaded source video and mark project as 'ready'
    for the user to configure Reel Settings before generation.
    """
    project_id = uuid.UUID(project_id_str)
    db = SyncSessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.source_file_key:
            return

        project.status = "probing"
        db.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_source = os.path.join(tmp_dir, "source.mp4")
            storage_service.download_file(project.source_file_key, local_source)
            probe_data = probe_media_file(local_source)

        project.duration = probe_data["duration"]
        project.probe_data = probe_data
        project.status = "ready"
        db.commit()
    except Exception as exc:
        logger.error(f"Failed to probe source for project {project_id}: {exc}")
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "failed"
            project.error_message = f"Failed to inspect uploaded video: {str(exc)}"
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True)
def run_analysis_pipeline(self, project_id_str: str):
    """
    Main analysis orchestrator:
    1. Probe media file if needed.
    2. Divide entire recording into overlapping chunks.
    3. Transcribe, scan visuals and audio peaks, call Gemini / heuristics.
    4. Reconcile boundaries, deduplicate candidates, create Reels in DB.
    5. Trigger video rendering for passing reels.
    """
    project_id = uuid.UUID(project_id_str)
    db = SyncSessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.source_file_key:
            logger.error(f"Project {project_id_str} not found or missing source media key.")
            return

        project.status = "analyzing"
        project.error_message = None
        db.commit()

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_source = os.path.join(tmp_dir, "source_media.mp4")
            logger.info(f"Downloading source media for project {project_id} from {project.source_file_key}...")
            storage_service.download_file(project.source_file_key, local_source)

            # Probe media if duration is not set
            if not project.duration or not project.probe_data:
                probe_data = probe_media_file(local_source)
                project.duration = probe_data["duration"]
                project.probe_data = probe_data
                db.commit()

            total_duration = project.duration or 0.0
            if total_duration <= 0:
                raise RuntimeError("Invalid or zero duration media.")

            # Chunking configuration (~5m45s chunks with 45s overlap)
            chunk_step = settings.CHUNK_DURATION_SECONDS - settings.CHUNK_OVERLAP_SECONDS # e.g. 300s
            chunk_len = settings.CHUNK_DURATION_SECONDS # e.g. 345s

            # Determine chunk intervals
            intervals = []
            curr_start = 0.0
            while curr_start < total_duration:
                curr_end = min(total_duration, curr_start + chunk_len)
                intervals.append((curr_start, curr_end))
                if curr_end >= total_duration:
                    break
                curr_start += chunk_step

            project.total_chunks = len(intervals)
            db.commit()

            # Ensure AnalysisChunk rows exist in DB (idempotent checkpointing)
            existing_chunks = {c.chunk_index: c for c in project.chunks}
            for idx, (c_start, c_end) in enumerate(intervals):
                if idx not in existing_chunks:
                    chunk_row = AnalysisChunk(
                        project_id=project.id,
                        chunk_index=idx,
                        start_time=c_start,
                        end_time=c_end,
                        status="pending",
                    )
                    db.add(chunk_row)
            db.commit()

            # Process chunks sequentially or bounded
            all_reconciled_words: List[Dict[str, Any]] = []
            raw_candidates: List[Dict[str, Any]] = []

            for idx, (c_start, c_end) in enumerate(intervals):
                chunk = db.query(AnalysisChunk).filter(
                    AnalysisChunk.project_id == project.id,
                    AnalysisChunk.chunk_index == idx
                ).first()

                if chunk.status == "completed" and chunk.transcript is not None:
                    logger.info(f"Reusing cached chunk {idx} for project {project_id}")
                    chunk_words = chunk.transcript
                    scene_changes = chunk.scene_changes or []
                    audio_peaks = chunk.audio_peaks or []
                    chunk_candidates = analyze_chunk_with_gemini(
                        transcript_words=chunk_words,
                        scene_changes=scene_changes,
                        audio_peaks=audio_peaks,
                        chunk_start=c_start,
                        chunk_end=c_end,
                    )
                    raw_candidates.extend(chunk_candidates)
                else:
                    chunk.status = "transcribing"
                    db.commit()

                    # Transcribe chunk
                    chunk_duration = c_end - c_start
                    chunk_words = transcribe_media_segment(
                        media_path=local_source,
                        start_time=c_start,
                        duration=chunk_duration,
                    )

                    # Visual & Audio scanning
                    chunk.status = "scanning"
                    db.commit()
                    scene_changes = detect_scene_changes(local_source, c_start, chunk_duration)
                    audio_peaks = detect_audio_peaks(local_source, c_start, chunk_duration)

                    # Gemini candidate discovery
                    chunk_candidates = analyze_chunk_with_gemini(
                        transcript_words=chunk_words,
                        scene_changes=scene_changes,
                        audio_peaks=audio_peaks,
                        chunk_start=c_start,
                        chunk_end=c_end,
                    )
                    raw_candidates.extend(chunk_candidates)

                    # Save chunk data
                    chunk.transcript = chunk_words
                    chunk.scene_changes = scene_changes
                    chunk.audio_peaks = audio_peaks
                    chunk.status = "completed"
                    db.commit()

                # Reconcile transcript overlap
                if idx == 0:
                    all_reconciled_words = chunk_words
                else:
                    overlap_start = c_start
                    overlap_end = intervals[idx - 1][1]
                    all_reconciled_words = reconcile_transcript_words(
                        existing_words=all_reconciled_words,
                        new_words=chunk_words,
                        overlap_start=overlap_start,
                        overlap_end=overlap_end,
                    )

                # Update project progress
                project.completed_chunks = idx + 1
                project.analyzed_duration = min(total_duration, c_end)
                db.commit()

            # Deduplicate candidates across all chunks
            unique_candidates = deduplicate_candidates(raw_candidates, iou_threshold=0.5)

            # If no candidates met criteria or were found, ensure at least one candidate is proposed if duration allows
            if not unique_candidates and total_duration >= settings.MIN_CLIP_DURATION:
                sample_end = min(total_duration, 45.0)
                unique_candidates.append({
                    "start_time": 0.0,
                    "end_time": round(sample_end, 2),
                    "clip_duration": round(sample_end, 2),
                    "top_caption": "HIGHLIGHT CLIP",
                    "category": "highlight",
                    "reason": "Initial full segment highlight",
                    "score_hook": 70.0,
                    "score_payoff": 70.0,
                    "score_clarity": 70.0,
                    "score_entertainment": 70.0,
                    "overall_score": 70.0,
                    "source": "fallback",
                })

            # Existing reels check to avoid duplicates on restart
            existing_reels = db.query(Reel).filter(Reel.project_id == project.id).all()
            existing_ranges = {(round(r.source_start, 1), round(r.source_end, 1)) for r in existing_reels}

            reels_to_render = []
            for cand in unique_candidates:
                key_range = (round(cand["start_time"], 1), round(cand["end_time"], 1))
                if key_range in existing_ranges:
                    continue

                from app.services.romanizer import romanize_words, romanize_text
                subtitles = build_clip_subtitles(
                    all_words=all_reconciled_words,
                    clip_start=cand["start_time"],
                    clip_end=cand["end_time"],
                )
                subtitles = romanize_words(subtitles)

                score = cand["overall_score"]
                is_borderline = score < settings.DEFAULT_MIN_SCORE
                top_caption_clean = romanize_text(cand["top_caption"])

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

                reel = Reel(
                    project_id=project.id,
                    title=top_caption_clean,
                    reason=str(cand["reason"]),
                    category=str(cand["category"]),
                    source_start=float(cand["start_time"]),
                    source_end=float(cand["end_time"]),
                    clip_duration=float(cand["clip_duration"]),
                    score=float(score),
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
                reels_to_render.append(reel.id)

            project.status = "completed"
            db.commit()

            # Trigger background render tasks for qualifying reels
            for reel_id in reels_to_render:
                render_reel_task.delay(str(reel_id))

    except Exception as e:
        logger.error(f"Analysis pipeline error for project {project_id}: {e}")
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "failed"
            project.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def render_reel_task(self, reel_id_str: str):
    """
    Renders a single 1080x1920 vertical reel, extracts thumbnail, uploads to MinIO.
    Idempotent and isolated per reel.
    """
    reel_id = uuid.UUID(reel_id_str)
    db = SyncSessionLocal()

    try:
        reel = db.query(Reel).filter(Reel.id == reel_id).first()
        if not reel:
            return

        reel.render_status = "rendering"
        reel.render_progress = 10.0
        db.commit()

        project = reel.project
        source_key = reel.source_media_key or (project.source_file_key if project else None)
        if not source_key:
            raise RuntimeError("Project or clip source media not found.")

        # Check for direct zero-copy access to source video on local storage volume
        local_direct = storage_service.get_local_path(source_key)
        if local_direct and os.path.exists(local_direct):
            local_source = local_direct
            logger.info(f"Using direct zero-copy disk path for {source_key}: {local_source}")
        else:
            cache_dir = "/tmp/reelstudio_cache"
            os.makedirs(cache_dir, exist_ok=True)
            safe_proj_id = str(project.id) if project else "global"
            cache_filename = f"{safe_proj_id}_{os.path.basename(source_key)}"
            cached_source = os.path.join(cache_dir, cache_filename)

            # Check if source media is already cached locally
            expected_size = storage_service.get_object_size(source_key)
            if not os.path.exists(cached_source) or os.path.getsize(cached_source) != expected_size:
                logger.info(f"Downloading source media {source_key} ({expected_size / (1024*1024):.1f} MB) to worker cache...")
                storage_service.download_file(source_key, cached_source)
            else:
                logger.info(f"Using locally cached source media for project {safe_proj_id}")
            local_source = cached_source

        with tempfile.TemporaryDirectory() as tmp_dir:
            local_rendered = os.path.join(tmp_dir, f"rendered_{reel.id}.mp4")
            local_thumb = os.path.join(tmp_dir, f"thumb_{reel.id}.jpg")

            reel.render_progress = 30.0
            db.commit()

            has_audio = bool(project.probe_data.get("has_audio", True)) if (project and project.probe_data) else True
            start_offset = 0.0 if reel.source_media_key else reel.source_start

            # Render vertical video with burned captions & karaoke subtitles
            render_reel_video(
                source_media_path=local_source,
                output_mp4_path=local_rendered,
                source_start=start_offset,
                clip_duration=reel.clip_duration,
                framing_mode=reel.framing_mode,
                pan_x_offset=reel.pan_x_offset,
                top_caption=reel.top_caption,
                subtitles_words=reel.subtitles_json,
                subtitle_font_size=reel.subtitle_font_size or 54,
                has_audio=has_audio,
                split_facecam_crop=reel.split_facecam_crop,
                split_gameplay_crop=reel.split_gameplay_crop,
                split_order=reel.split_order or "facecam_top",
                split_ratio=reel.split_ratio or 0.35,
                subtitle_position=reel.subtitle_position or "bottom",
                subtitle_y_percent=reel.subtitle_y_percent if reel.subtitle_y_percent is not None else 0.82,
                subtitle_color=reel.subtitle_color or "#FFE500",
                subtitle_font_family=reel.subtitle_font_family or "Noto Sans",
            )
            reel.render_progress = 80.0
            db.commit()

            # Extract thumbnail
            extract_keyframe(
                media_path=local_rendered,
                timestamp=min(1.0, reel.clip_duration / 2.0),
                output_path=local_thumb,
                width=540,
            )

            # Upload rendered video & thumbnail to MinIO
            video_key = f"projects/{project.id}/reels/{reel.id}.mp4"
            thumb_key = f"projects/{project.id}/reels/{reel.id}_thumb.jpg"

            storage_service.upload_file(local_rendered, video_key, content_type="video/mp4")
            if os.path.exists(local_thumb):
                storage_service.upload_file(local_thumb, thumb_key, content_type="image/jpeg")

            reel.video_key = video_key
            reel.thumbnail_key = thumb_key if os.path.exists(local_thumb) else None
            reel.render_status = "completed"
            reel.render_progress = 100.0
            reel.render_error = None
            db.commit()
            logger.info(f"Reel {reel.id} rendering completed.")

    except Exception as e:
        logger.error(f"Render failed for reel {reel_id}: {e}")
        reel = db.query(Reel).filter(Reel.id == reel_id).first()
        if reel:
            reel.render_status = "failed"
            reel.render_error = str(e)
            db.commit()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=5)
    finally:
        db.close()


@celery_app.task
def process_bulk_zip_export(export_id_str: str):
    """
    Background worker task to package all completed reels into a ZIP archive.
    """
    export_id = uuid.UUID(export_id_str)
    db = SyncSessionLocal()
    try:
        bulk_export = db.query(BulkExport).filter(BulkExport.id == export_id).first()
        if not bulk_export:
            return

        bulk_export.status = "processing"
        db.commit()

        project = bulk_export.project
        completed_reels = db.query(Reel).filter(
            Reel.project_id == project.id,
            Reel.render_status == "completed",
            Reel.video_key.isnot(None),
        ).all()

        if not completed_reels:
            bulk_export.status = "failed"
            bulk_export.error_message = "No completed reels available to export."
            db.commit()
            return

        reels_data = [{"video_key": r.video_key, "title": r.title} for r in completed_reels]
        zip_key = f"projects/{project.id}/exports/{bulk_export.id}.zip"

        create_reels_zip_archive(
            reel_items=reels_data,
            zip_output_key=zip_key,
            project_title=project.title,
        )

        bulk_export.zip_key = zip_key
        bulk_export.reel_count = len(completed_reels)
        bulk_export.status = "completed"
        db.commit()

    except Exception as e:
        logger.error(f"Bulk zip export failed: {e}")
        bulk_export = db.query(BulkExport).filter(BulkExport.id == export_id).first()
        if bulk_export:
            bulk_export.status = "failed"
            bulk_export.error_message = str(e)
            db.commit()
    finally:
        db.close()
