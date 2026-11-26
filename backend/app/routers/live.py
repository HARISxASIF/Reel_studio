import os
import uuid
import tempfile
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.live_session import LiveSession
from app.models.reel import Reel
from app.schemas.live import (
    LiveProbeRequest,
    LiveProbeResponse,
    LiveCreateProjectRequest,
    LiveSessionResponse,
    LiveStartRequest,
    LiveManualClipRequest,
)
from app.schemas.project import ProjectResponse
from app.services.auth import get_current_user
from app.services.storage import storage_service
from app.services.live_detector import probe_live_stream_source, extract_live_preview_frame
from app.services.gemini_limiter import gemini_limiter
from app.routers.projects import validate_project_settings
from app.tasks.live_pipeline import capture_and_process_live_stream_task, create_manual_live_clip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live"])


@router.post("/probe", response_model=LiveProbeResponse)
async def probe_live_source(
    req: LiveProbeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Safely probe a live stream URL (YouTube Live, Twitch, Kick, direct HLS)
    with SSRF protection. Returns platform capability, message, and preview frame.
    """
    try:
        probe_res = await probe_live_stream_source(req.url)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Live probe error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to probe live source: {str(e)}")

    preview_frame_url = None
    resolved_url = probe_res.get("resolved_stream_url")

    # If stream is live and available, capture a preview frame for layout setup
    if probe_res.get("capability") == "live_available" and resolved_url:
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_img = os.path.join(tmp_dir, "preview.jpg")
                if extract_live_preview_frame(resolved_url, tmp_img):
                    preview_key = f"live_previews/{uuid.uuid4()}.jpg"
                    storage_service.upload_file(tmp_img, preview_key, content_type="image/jpeg")
                    preview_frame_url = storage_service.generate_presigned_download_url(preview_key, expires_in=7200)
        except Exception as e:
            logger.warning(f"Failed to generate live preview frame: {e}")

    return LiveProbeResponse(
        url=req.url,
        platform=probe_res.get("platform", "direct_hls"),
        capability=probe_res.get("capability", "media_unavailable"),
        message=probe_res.get("message", ""),
        title=probe_res.get("title"),
        thumbnail_url=probe_res.get("thumbnail_url"),
        resolved_stream_url=resolved_url,
        preview_frame_url=preview_frame_url,
    )


@router.post("/projects", response_model=Dict[str, Any])
async def create_live_project(
    req: LiveCreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project in 'ready' state configured for Live Streaming.
    Requires user to confirm Reel Settings before clicking Start Live Clipping.
    """
    try:
        probe_res = await probe_live_stream_source(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid live stream URL: {str(e)}")

    title = req.title or probe_res.get("title") or "Live Stream Project"
    resolved_url = probe_res.get("resolved_stream_url")

    preview_key = None
    if probe_res.get("capability") == "live_available":
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_img = os.path.join(tmp_dir, "preview.jpg")
                extracted = False
                if resolved_url:
                    extracted = extract_live_preview_frame(resolved_url, tmp_img)
                if not extracted and probe_res.get("thumbnail_url"):
                    import httpx
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(probe_res["thumbnail_url"])
                        if resp.status_code == 200:
                            with open(tmp_img, "wb") as f:
                                f.write(resp.content)
                            extracted = True
                if extracted and os.path.exists(tmp_img) and os.path.getsize(tmp_img) > 0:
                    preview_key = f"live_previews/{uuid.uuid4()}.jpg"
                    storage_service.upload_file(tmp_img, preview_key, content_type="image/jpeg")
        except Exception as e:
            logger.warning(f"Failed to generate live preview frame: {e}")

    # Create Project in 'ready' state (waiting for user settings confirmation)
    project = Project(
        user_id=current_user.id,
        title=title,
        source_type="live_stream",
        source_url=req.url,
        status="ready",
        framing_mode="crop",
        pan_x_offset=0.0,
        subtitle_font_size=54,
    )
    db.add(project)
    await db.flush()

    # Create associated LiveSession
    session = LiveSession(
        project_id=project.id,
        status="ready",
        feed_url=req.url,
        resolved_stream_url=resolved_url,
        platform=probe_res.get("platform", "direct_hls"),
        capability=probe_res.get("capability", "media_unavailable"),
        capability_message=probe_res.get("message"),
        preview_frame_key=preview_key,
    )
    db.add(session)
    await db.commit()
    await db.refresh(project)
    await db.refresh(session)

    preview_url = storage_service.generate_presigned_download_url(preview_key) if preview_key else None

    return {
        "project": ProjectResponse.model_validate(project),
        "session": LiveSessionResponse.model_validate(session),
        "preview_frame_url": preview_url,
    }


@router.get("/projects/{project_id}", response_model=LiveSessionResponse)
async def get_live_session(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get real-time live session status, timeline marks, and AI backlog.
    Automatically ensures preview frame is extracted if stream is ready.
    """
    res = await db.execute(
        select(LiveSession)
        .join(Project)
        .where(LiveSession.project_id == project_id, Project.user_id == current_user.id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found for this project.")

    # On-demand backfill preview frame if missing and stream is available
    if not session.preview_frame_key and session.capability == "live_available":
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_img = os.path.join(tmp_dir, "preview.jpg")
                extracted = False
                if session.resolved_stream_url:
                    extracted = extract_live_preview_frame(session.resolved_stream_url, tmp_img)
                if not extracted:
                    probe = await probe_live_stream_source(session.feed_url)
                    thumb_url = probe.get("thumbnail_url")
                    if thumb_url:
                        import httpx
                        with httpx.Client(timeout=10.0) as client:
                            resp = client.get(thumb_url)
                            if resp.status_code == 200:
                                with open(tmp_img, "wb") as f:
                                    f.write(resp.content)
                                extracted = True
                if extracted and os.path.exists(tmp_img) and os.path.getsize(tmp_img) > 0:
                    preview_key = f"live_previews/{uuid.uuid4()}.jpg"
                    storage_service.upload_file(tmp_img, preview_key, content_type="image/jpeg")
                    session.preview_frame_key = preview_key
                    await db.commit()
        except Exception as e:
            logger.warning(f"On-demand live preview frame generation failed: {e}")

    session_resp = LiveSessionResponse.model_validate(session)
    if session.preview_frame_key:
        session_resp.preview_frame_url = storage_service.generate_presigned_download_url(session.preview_frame_key)
    return session_resp


@router.post("/projects/{project_id}/start", response_model=LiveSessionResponse)
async def start_live_clipping(
    project_id: uuid.UUID,
    req: LiveStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm Reel Settings and launch background live stream capture & clipping.
    Snapshots settings into the session. Idempotent on double-click or reload.
    """
    res = await db.execute(
        select(Project, LiveSession)
        .join(LiveSession, Project.id == LiveSession.project_id)
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Project or live session not found.")
    project, session = row

    if session.capability != "live_available":
        raise HTTPException(status_code=400, detail=f"Cannot start clipping: stream is {session.capability}. {session.capability_message}")

    # Validate settings if provided
    settings_dict = {}
    if req.settings:
        st = req.settings
        validate_project_settings(
            framing_mode=st.framing_mode,
            pan_x_offset=st.pan_x_offset,
            subtitle_font_size=st.subtitle_font_size,
            split_facecam_crop=st.split_facecam_crop,
            split_gameplay_crop=st.split_gameplay_crop,
            subtitle_position=st.subtitle_position,
            subtitle_y_percent=st.subtitle_y_percent,
            subtitle_color=st.subtitle_color,
            subtitle_font_family=st.subtitle_font_family,
        )
        if st.framing_mode is not None:
            project.framing_mode = st.framing_mode
        if st.pan_x_offset is not None:
            project.pan_x_offset = st.pan_x_offset
        if st.subtitle_font_size is not None:
            project.subtitle_font_size = st.subtitle_font_size
        if st.subtitle_position is not None:
            if st.subtitle_position in ("bottom", "middle", "top"):
                project.subtitle_position = st.subtitle_position
        if st.subtitle_y_percent is not None:
            project.subtitle_y_percent = max(0.1, min(0.95, st.subtitle_y_percent))
        if st.subtitle_color is not None:
            project.subtitle_color = st.subtitle_color
        if st.subtitle_font_family is not None:
            project.subtitle_font_family = st.subtitle_font_family
        if st.split_facecam_crop is not None:
            project.split_facecam_crop = st.split_facecam_crop
        if st.split_gameplay_crop is not None:
            project.split_gameplay_crop = st.split_gameplay_crop
        if st.split_order is not None:
            project.split_order = st.split_order
        if st.split_ratio is not None:
            project.split_ratio = st.split_ratio

        settings_dict = {
            "framing_mode": project.framing_mode,
            "pan_x_offset": project.pan_x_offset,
            "subtitle_font_size": project.subtitle_font_size,
            "subtitle_position": project.subtitle_position,
            "subtitle_y_percent": project.subtitle_y_percent,
            "subtitle_color": project.subtitle_color,
            "subtitle_font_family": project.subtitle_font_family,
            "split_facecam_crop": project.split_facecam_crop,
            "split_gameplay_crop": project.split_gameplay_crop,
            "split_order": project.split_order,
            "split_ratio": project.split_ratio,
        }
    else:
        settings_dict = {
            "framing_mode": project.framing_mode,
            "pan_x_offset": project.pan_x_offset,
            "subtitle_font_size": project.subtitle_font_size,
            "subtitle_position": project.subtitle_position,
            "subtitle_y_percent": project.subtitle_y_percent,
            "subtitle_color": project.subtitle_color,
            "subtitle_font_family": project.subtitle_font_family,
            "split_facecam_crop": project.split_facecam_crop,
            "split_gameplay_crop": project.split_gameplay_crop,
            "split_order": project.split_order,
            "split_ratio": project.split_ratio,
        }

    # Snapshot settings
    project.settings_snapshot = settings_dict
    session.settings_snapshot = settings_dict
    session.status = "capturing"
    project.status = "analyzing"
    await db.commit()
    await db.refresh(session)

    # Launch Celery task asynchronously
    capture_and_process_live_stream_task.delay(str(session.id))

    session_resp = LiveSessionResponse.model_validate(session)
    if session.preview_frame_key:
        session_resp.preview_frame_url = storage_service.generate_presigned_download_url(session.preview_frame_key)
    return session_resp


@router.post("/projects/{project_id}/stop")
async def stop_live_clipping(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stop Live Clipping: stops new segment capture and drains analysis
    for footage already captured.
    """
    res = await db.execute(
        select(LiveSession)
        .join(Project)
        .where(LiveSession.project_id == project_id, Project.user_id == current_user.id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found.")

    if session.status in ("stopped", "ended"):
        return {"status": session.status, "message": "Live session is already stopped."}

    session.status = "draining"
    session.capability_message = "Stopping capture. Draining pending analysis..."
    await db.commit()

    return {"status": "draining", "message": "Live capture stopping. Draining pending analysis..."}


@router.post("/projects/{project_id}/clip-last")
async def clip_last_buffer(
    project_id: uuid.UUID,
    req: LiveManualClipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manual 'Clip last 60 seconds' action from the live rolling buffer.
    Requires at least 30 seconds of continuous buffer footage.
    """
    res = await db.execute(
        select(LiveSession)
        .join(Project)
        .where(LiveSession.project_id == project_id, Project.user_id == current_user.id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found.")

    if session.continuous_buffer_seconds < 30.0:
        raise HTTPException(
            status_code=400,
            detail=f"At least 30 continuous seconds required. Currently {session.continuous_buffer_seconds:.1f}s available.",
        )

    try:
        reel_id = create_manual_live_clip(str(session.id), duration=req.duration)
        if not reel_id:
            raise HTTPException(status_code=500, detail="Failed to create manual clip.")
        return {"reel_id": reel_id, "message": "Manual live reel queued for rendering."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Manual clip error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create manual clip: {str(e)}")


@router.get("/limiter")
async def get_limiter_status():
    """
    Get current shared Gemini rate limiter metrics across all jobs.
    """
    return gemini_limiter.get_status()
