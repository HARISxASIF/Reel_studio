import os
import uuid
import time
import tempfile
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from app.tasks.celery_app import celery_app
from app.tasks.pipeline import render_reel_task
from app.database import SyncSessionLocal
from app.models.project import Project
from app.models.reel import Reel
from app.models.live_session import LiveSession
from app.services.storage import storage_service
from app.services.live_buffer import LiveBufferManager
from app.services.live_detector import resolve_relative_url
from app.services.url_importer import validate_url_security
from app.services.transcription import transcribe_media_segment, reconcile_transcript_words
from app.services.visual_audio import detect_scene_changes, detect_audio_peaks
from app.services.gemini import analyze_chunk_with_gemini
from app.services.gemini_limiter import gemini_limiter
from app.services.candidate import deduplicate_candidates, build_clip_subtitles
from app.services.romanizer import romanize_words, romanize_text
from app.config import settings

logger = logging.getLogger(__name__)


def _get_redis_lock(lock_key: str, ttl: int = 3600):
    import redis
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        acquired = r.set(lock_key, "1", nx=True, ex=ttl)
        return r, bool(acquired)
    except Exception as e:
        logger.warning(f"Redis lock error: {e}")
        return None, True


@celery_app.task(bind=True)
def capture_and_process_live_stream_task(self, session_id_str: str):
    """
    Long-running Celery worker task that ingests an ongoing live stream,
    maintains a rolling buffer, transcribes incrementally, calls Gemini/limiter,
    and creates standalone 30-60s reels while stream continues.
    """
    session_id = uuid.UUID(session_id_str)
    lock_key = f"live_session:lock:{session_id}"
    r_client, acquired = _get_redis_lock(lock_key, ttl=7200)

    if not acquired:
        logger.info(f"Capture task for session {session_id} is already running. Exiting duplicate invocation.")
        return

    db = SyncSessionLocal()
    buffer_manager = LiveBufferManager(str(session_id))
    all_session_words: List[Dict[str, Any]] = []

    try:
        session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
        if not session:
            logger.error(f"LiveSession {session_id} not found.")
            return

        project = session.project
        if not project:
            logger.error(f"Parent project for session {session_id} not found.")
            return

        # Check concurrency limit
        active_sessions = db.query(LiveSession).filter(
            LiveSession.status == "capturing",
            LiveSession.id != session_id
        ).count()
        if active_sessions >= settings.LIVE_MAX_CONCURRENT_SESSIONS:
            session.status = "failed"
            session.capability_message = f"Maximum live stream concurrency limit ({settings.LIVE_MAX_CONCURRENT_SESSIONS}) reached. Please stop an active session first."
            db.commit()
            return

        session.status = "capturing"
        session.capture_started_at = datetime.utcnow()
        session.capability_message = "Live stream capture and AI clipping active."
        project.status = "analyzing"
        db.commit()

        stream_url = session.resolved_stream_url or session.feed_url
        analyzed_timeline_mark = 0.0
        backlogged_windows: List[Dict[str, Any]] = []
        is_stream_ended = False

        logger.info(f"Starting live ingestion loop for session {session_id} from {stream_url}...")

        while True:
            # 1. Refresh session status from DB to check for user Stop command
            db.refresh(session)
            if session.status in ("draining", "stopped", "ended", "failed"):
                logger.info(f"Session {session_id} status changed to '{session.status}'. Draining remaining work...")
                break

            # 2. Fetch HLS manifest safely with SSRF check
            try:
                validate_url_security(stream_url)
                with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                    resp = client.get(stream_url)
                    validate_url_security(str(resp.url))
                    if resp.status_code == 200:
                        manifest_text = resp.text
                        if "#EXT-X-ENDLIST" in manifest_text:
                            logger.info(f"Detected #EXT-X-ENDLIST for session {session_id}. Stream broadcast has ended.")
                            is_stream_ended = True

                        # Parse segments and media sequence
                        media_seq = None
                        lines = manifest_text.splitlines()
                        for line in lines:
                            line_s = line.strip()
                            if line_s.startswith("#EXT-X-MEDIA-SEQUENCE:"):
                                try:
                                    media_seq = int(line_s.split(":")[1].strip())
                                except ValueError:
                                    pass

                        # Download new segments
                        curr_extinf_dur = 4.0
                        seq_counter = media_seq or 0
                        for line in lines:
                            line_s = line.strip()
                            if line_s.startswith("#EXTINF:"):
                                try:
                                    dur_str = line_s.split(":")[1].split(",")[0].strip()
                                    curr_extinf_dur = float(dur_str)
                                except Exception:
                                    curr_extinf_dur = 4.0
                            elif line_s and not line_s.startswith("#"):
                                seg_url = resolve_relative_url(str(resp.url), line_s)
                                seg = buffer_manager.download_segment_safe(
                                    segment_url=seg_url,
                                    extinf_duration=curr_extinf_dur,
                                    media_sequence=seq_counter,
                                )
                                seq_counter += 1

            except Exception as e:
                logger.warning(f"Error fetching live manifest for session {session_id}: {e}")

            # 3. Update session metrics in DB
            session.total_captured_seconds = buffer_manager.total_captured_seconds
            session.last_captured_timestamp = buffer_manager.total_captured_seconds
            session.continuous_buffer_seconds = buffer_manager.continuous_buffer_seconds
            session.coverage_gaps = buffer_manager.coverage_gaps
            session.storage_used_bytes = buffer_manager.get_storage_used_bytes()
            db.commit()

            # 4. Incremental Analysis: Evaluate overlapping 60-second windows
            window_size = float(settings.LIVE_ANALYSIS_WINDOW_SECONDS)  # e.g. 60s
            step_size = float(settings.LIVE_ANALYSIS_STEP_SECONDS)      # e.g. 20s

            # Form any new eligible windows
            while (buffer_manager.total_captured_seconds - analyzed_timeline_mark) >= window_size:
                w_start = analyzed_timeline_mark
                w_end = analyzed_timeline_mark + window_size
                backlogged_windows.append({
                    "start": w_start,
                    "end": w_end,
                })
                analyzed_timeline_mark += step_size

            session.ai_backlog_count = len(backlogged_windows)

            # Update safe timeline mark so rolling buffer never purges segments needed by backlog
            oldest_needed = backlogged_windows[0]["start"] if backlogged_windows else analyzed_timeline_mark
            buffer_manager.purge_expired_segments(min_safe_timeline_mark=oldest_needed)

            # 5. Process backlogged analysis windows
            if backlogged_windows:
                # Check Gemini quota limiter
                allowed, wait_secs, reason = gemini_limiter.check_quota(estimated_tokens=2500)
                if not allowed:
                    session.ai_status = "rate_limited"
                    session.capability_message = f"AI quota limiter active: {reason}. Preserving media buffer while queue drains."
                    db.commit()
                else:
                    session.ai_status = "analyzing"
                    db.commit()

                    curr_win = backlogged_windows.pop(0)
                    win_start = curr_win["start"]
                    win_end = curr_win["end"]

                    try:
                        with tempfile.TemporaryDirectory() as win_tmp:
                            tmp_win_media = os.path.join(win_tmp, "window.mp4")
                            extracted = buffer_manager.extract_clip_media(win_start, win_end, tmp_win_media)

                            if extracted and os.path.exists(tmp_win_media):
                                # Transcribe window
                                words = transcribe_media_segment(
                                    media_path=tmp_win_media,
                                    start_time=0.0,
                                    duration=(win_end - win_start),
                                )
                                # Align words to session timeline
                                for w in words:
                                    w["start"] = round(w["start"] + win_start, 2)
                                    w["end"] = round(w["end"] + win_start, 2)

                                all_session_words.extend(words)

                                # Visual & audio signal detection
                                scene_changes = detect_scene_changes(tmp_win_media, 0.0, (win_end - win_start))
                                scene_changes = [round(sc + win_start, 2) for sc in scene_changes]
                                audio_peaks = detect_audio_peaks(tmp_win_media, 0.0, (win_end - win_start))

                                # Gemini / heuristic analysis
                                candidates = analyze_chunk_with_gemini(
                                    transcript_words=words,
                                    scene_changes=scene_changes,
                                    audio_peaks=audio_peaks,
                                    chunk_start=win_start,
                                    chunk_end=win_end,
                                )

                                # Existing reels check for deduplication across overlapping windows
                                db.refresh(project)
                                existing_ranges = {(round(r.source_start, 1), round(r.source_end, 1)) for r in project.reels}

                                for cand in candidates:
                                    c_start = cand["start_time"]
                                    c_end = cand["end_time"]
                                    c_dur = c_end - c_start

                                    # Verify 30-60s duration
                                    if c_dur < settings.MIN_CLIP_DURATION or c_dur > settings.MAX_CLIP_DURATION:
                                        continue

                                    # Ensure trailing context is fully captured before finalizing
                                    if c_end > (buffer_manager.total_captured_seconds - 2.0) and not is_stream_ended:
                                        # Put window back to wait for trailing footage
                                        backlogged_windows.insert(0, curr_win)
                                        break

                                    # Deduplicate
                                    key_range = (round(c_start, 1), round(c_end, 1))
                                    if key_range in existing_ranges:
                                        continue
                                    existing_ranges.add(key_range)

                                    # Extract and persist permanent source clip media
                                    reel_id = uuid.uuid4()
                                    clip_tmp_path = os.path.join(win_tmp, f"clip_{reel_id}.mp4")
                                    clip_extracted = buffer_manager.extract_clip_media(
                                        start_time=c_start,
                                        end_time=c_end,
                                        output_path=clip_tmp_path,
                                        reel_id=str(reel_id),
                                    )
                                    if not clip_extracted:
                                        logger.warning(f"Could not extract clip media for candidate {c_start}-{c_end}")
                                        continue

                                    clip_storage_key = f"projects/{project.id}/reels/{reel_id}_source.mp4"
                                    storage_service.upload_file(clip_tmp_path, clip_storage_key, content_type="video/mp4")

                                    # Subtitles and romanization
                                    subs = build_clip_subtitles(
                                        all_words=all_session_words,
                                        clip_start=c_start,
                                        clip_end=c_end,
                                    )
                                    subs = romanize_words(subs)
                                    top_cap = romanize_text(cand["top_caption"])

                                    snapshot = session.settings_snapshot or project.settings_snapshot or {}
                                    reel_framing = snapshot.get("framing_mode", project.framing_mode or "crop")
                                    reel_pan = snapshot.get("pan_x_offset", project.pan_x_offset or 0.0)
                                    reel_font = snapshot.get("subtitle_font_size", project.subtitle_font_size or 54)
                                    reel_fc = snapshot.get("split_facecam_crop", project.split_facecam_crop)
                                    reel_gp = snapshot.get("split_gameplay_crop", project.split_gameplay_crop)
                                    reel_order = snapshot.get("split_order", project.split_order or "facecam_top")
                                    reel_ratio = snapshot.get("split_ratio", project.split_ratio or 0.35)
                                    reel_sub_pos = snapshot.get("subtitle_position", project.subtitle_position or "bottom")
                                    reel_sub_y = snapshot.get("subtitle_y_percent", project.subtitle_y_percent if project.subtitle_y_percent is not None else 0.82)
                                    reel_sub_col = snapshot.get("subtitle_color", project.subtitle_color or "#FFE500")
                                    reel_sub_font = snapshot.get("subtitle_font_family", project.subtitle_font_family or "Noto Sans")

                                    reel = Reel(
                                        id=reel_id,
                                        project_id=project.id,
                                        title=top_cap,
                                        reason=cand["reason"],
                                        category=cand["category"],
                                        source_start=c_start,
                                        source_end=c_end,
                                        clip_duration=round(c_dur, 2),
                                        score=cand["overall_score"],
                                        score_hook=cand["score_hook"],
                                        score_payoff=cand["score_payoff"],
                                        score_clarity=cand["score_clarity"],
                                        score_entertainment=cand["score_entertainment"],
                                        is_borderline=cand["overall_score"] < settings.DEFAULT_MIN_SCORE,
                                        framing_mode=reel_framing,
                                        pan_x_offset=reel_pan,
                                        top_caption=top_cap,
                                        subtitles_json=subs,
                                        subtitle_font_size=reel_font,
                                        subtitle_position=reel_sub_pos,
                                        subtitle_y_percent=reel_sub_y,
                                        subtitle_color=reel_sub_col,
                                        subtitle_font_family=reel_sub_font,
                                        split_facecam_crop=reel_fc,
                                        split_gameplay_crop=reel_gp,
                                        split_order=reel_order,
                                        split_ratio=reel_ratio,
                                        source_media_key=clip_storage_key,
                                        is_live_clip=True,
                                        render_status="pending",
                                    )
                                    db.add(reel)
                                    db.commit()

                                    # Queue background render
                                    render_reel_task.delay(str(reel.id))
                                    logger.info(f"Created live reel {reel.id} ({c_start:.1f}s - {c_end:.1f}s): {top_cap}")

                    except Exception as win_err:
                        logger.warning(f"Error processing live window {win_start:.1f}s - {win_end:.1f}s in session {session_id}: {win_err}", exc_info=True)

                    session.last_analyzed_timestamp = win_end
                    session.ai_status = "idle"
                    session.ai_backlog_count = len(backlogged_windows)
                    db.commit()

            if is_stream_ended:
                logger.info("Stream broadcast ended. Finalizing session.")
                break

            time.sleep(2.5)

        # 6. Drain completed: finalize session status
        db.refresh(session)
        if session.status == "draining" or is_stream_ended:
            session.status = "stopped" if not is_stream_ended else "ended"
            session.capture_stopped_at = datetime.utcnow()
            session.capability_message = "Live session finished. All qualifying reels generated and preserved."
            project.status = "completed"
            db.commit()

    except Exception as exc:
        logger.error(f"Fatal error in live stream capture task {session_id}: {exc}", exc_info=True)
        try:
            db.refresh(session)
            session.status = "failed"
            session.capability_message = f"Capture failed: {str(exc)}"
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
        if r_client:
            try:
                r_client.delete(lock_key)
            except Exception:
                pass


def create_manual_live_clip(session_id_str: str, duration: float = 60.0) -> Optional[str]:
    """
    Manual 'Clip last 60 seconds' action:
    Extracts the most recent footage from the live buffer, creates Reel, and queues render.
    """
    session_id = uuid.UUID(session_id_str)
    db = SyncSessionLocal()
    buffer_manager = LiveBufferManager(str(session_id))

    try:
        session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
        if not session or not session.project:
            return None

        project = session.project
        total_captured = session.total_captured_seconds
        continuous = session.continuous_buffer_seconds

        if continuous < settings.LIVE_MIN_MANUAL_CLIP_SECONDS:
            raise ValueError(f"At least {settings.LIVE_MIN_MANUAL_CLIP_SECONDS}s of continuous buffer required. Currently {continuous:.1f}s available.")

        clip_dur = min(duration, continuous, settings.MAX_CLIP_DURATION)
        clip_dur = max(clip_dur, settings.MIN_CLIP_DURATION)
        clip_end = total_captured
        clip_start = max(0.0, clip_end - clip_dur)

        reel_id = uuid.uuid4()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_clip_path = os.path.join(tmp_dir, f"manual_{reel_id}.mp4")
            extracted = buffer_manager.extract_clip_media(
                start_time=clip_start,
                end_time=clip_end,
                output_path=tmp_clip_path,
                reel_id=str(reel_id),
            )
            if not extracted:
                raise RuntimeError("Failed to extract manual clip from rolling buffer.")

            clip_storage_key = f"projects/{project.id}/reels/{reel_id}_source.mp4"
            storage_service.upload_file(tmp_clip_path, clip_storage_key, content_type="video/mp4")

            # Quick transcription for subtitles
            words = transcribe_media_segment(tmp_clip_path, start_time=0.0, duration=clip_dur)
            for w in words:
                w["start"] = round(w["start"], 2)
                w["end"] = round(w["end"], 2)

            subs = romanize_words(words)
            top_cap = f"LIVE STREAM MOMENT ({int(clip_start)}s)"

            snapshot = session.settings_snapshot or project.settings_snapshot or {}
            reel = Reel(
                id=reel_id,
                project_id=project.id,
                title=top_cap,
                reason="Manual clip triggered by user from live stream buffer",
                category="highlight",
                source_start=clip_start,
                source_end=clip_end,
                clip_duration=round(clip_dur, 2),
                score=80.0,
                score_hook=80.0,
                score_payoff=80.0,
                score_clarity=80.0,
                score_entertainment=80.0,
                is_borderline=False,
                framing_mode=snapshot.get("framing_mode", project.framing_mode or "crop"),
                pan_x_offset=snapshot.get("pan_x_offset", project.pan_x_offset or 0.0),
                top_caption=top_cap,
                subtitles_json=subs,
                subtitle_font_size=snapshot.get("subtitle_font_size", project.subtitle_font_size or 54),
                split_facecam_crop=snapshot.get("split_facecam_crop", project.split_facecam_crop),
                split_gameplay_crop=snapshot.get("split_gameplay_crop", project.split_gameplay_crop),
                split_order=snapshot.get("split_order", project.split_order or "facecam_top"),
                split_ratio=snapshot.get("split_ratio", project.split_ratio or 0.35),
                source_media_key=clip_storage_key,
                is_live_clip=True,
                render_status="pending",
            )
            db.add(reel)
            db.commit()

            render_reel_task.delay(str(reel.id))
            return str(reel.id)

    finally:
        db.close()
