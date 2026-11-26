import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.schemas.reel import ReelResponse, ReelUpdate
from app.services.auth import get_current_user
from app.services.storage import storage_service
from app.tasks.pipeline import render_reel_task
from app.config import settings

router = APIRouter(prefix="/api/reels", tags=["reels"])


@router.get("/{id}", response_model=ReelResponse)
async def get_reel(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reel, Project.source_file_key)
        .join(Project, Reel.project_id == Project.id)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Reel not found")
    reel, source_file_key = row
    source_key = reel.source_media_key or source_file_key

    res = ReelResponse.model_validate(reel)
    if reel.video_key:
        res.video_url = storage_service.generate_presigned_download_url(reel.video_key)
    if reel.thumbnail_key:
        res.thumbnail_url = storage_service.generate_presigned_download_url(reel.thumbnail_key)
    if source_key:
        res.source_video_url = storage_service.generate_presigned_download_url(source_key, expires_in=7200)
    return res


@router.patch("/{id}", response_model=ReelResponse)
async def update_reel(
    id: uuid.UUID,
    req: ReelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reel)
        .join(Project)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    # If trim boundaries changed, validate 30-60s window
    new_start = req.source_start if req.source_start is not None else reel.source_start
    new_end = req.source_end if req.source_end is not None else reel.source_end
    new_dur = new_end - new_start

    if req.source_start is not None or req.source_end is not None:
        if new_dur < settings.MIN_CLIP_DURATION or new_dur > settings.MAX_CLIP_DURATION:
            raise HTTPException(
                status_code=400,
                detail=f"Duration must be between {settings.MIN_CLIP_DURATION} and {settings.MAX_CLIP_DURATION} seconds. Got {new_dur:.1f}s.",
            )
        reel.source_start = round(new_start, 2)
        reel.source_end = round(new_end, 2)
        reel.clip_duration = round(new_dur, 2)

    if req.top_caption is not None:
        reel.top_caption = req.top_caption
        reel.title = req.top_caption

    if req.framing_mode is not None:
        if req.framing_mode not in ("crop", "fit", "pan", "split"):
            raise HTTPException(status_code=400, detail="Invalid framing mode")
        reel.framing_mode = req.framing_mode

    if req.pan_x_offset is not None:
        reel.pan_x_offset = max(-1.0, min(1.0, req.pan_x_offset))

    if req.split_facecam_crop is not None:
        reel.split_facecam_crop = req.split_facecam_crop

    if req.split_gameplay_crop is not None:
        reel.split_gameplay_crop = req.split_gameplay_crop

    if req.split_order is not None:
        if req.split_order in ("facecam_top", "gameplay_top"):
            reel.split_order = req.split_order

    if req.split_ratio is not None:
        reel.split_ratio = max(0.1, min(0.9, req.split_ratio))

    if req.subtitle_font_size is not None:
        reel.subtitle_font_size = max(30, min(100, req.subtitle_font_size))

    if req.subtitle_position is not None:
        if req.subtitle_position in ("bottom", "middle", "top"):
            reel.subtitle_position = req.subtitle_position

    if req.subtitle_y_percent is not None:
        reel.subtitle_y_percent = max(0.1, min(0.95, req.subtitle_y_percent))

    if req.subtitle_color is not None:
        reel.subtitle_color = req.subtitle_color

    if req.subtitle_font_family is not None:
        reel.subtitle_font_family = req.subtitle_font_family

    if req.subtitles_json is not None:
        from app.services.romanizer import romanize_words
        reel.subtitles_json = romanize_words(req.subtitles_json)

    # Set status to pending and re-render only this reel
    reel.render_status = "pending"
    reel.render_progress = 0.0
    await db.commit()
    await db.refresh(reel)

    # Queue re-rendering
    render_reel_task.delay(str(reel.id))

    proj_res = await db.execute(select(Project.source_file_key).where(Project.id == reel.project_id))
    source_file_key = proj_res.scalar_one_or_none()
    source_key = reel.source_media_key or source_file_key

    res = ReelResponse.model_validate(reel)
    if reel.video_key:
        res.video_url = storage_service.generate_presigned_download_url(reel.video_key)
    if reel.thumbnail_key:
        res.thumbnail_url = storage_service.generate_presigned_download_url(reel.thumbnail_key)
    if source_key:
        res.source_video_url = storage_service.generate_presigned_download_url(source_key, expires_in=7200)
    return res


@router.post("/{id}/romanize", response_model=ReelResponse)
async def romanize_reel_subtitles(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ensure all subtitles and captions for this reel are in English/Latin letters
    (converting Urdu to Roman Urdu and Hindi to Hinglish).
    """
    result = await db.execute(
        select(Reel)
        .join(Project)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    from app.services.romanizer import romanize_words, romanize_text
    if reel.subtitles_json:
        reel.subtitles_json = romanize_words(reel.subtitles_json)
    if reel.top_caption:
        reel.top_caption = romanize_text(reel.top_caption)
        reel.title = reel.top_caption

    reel.render_status = "pending"
    reel.render_progress = 0.0
    await db.commit()
    await db.refresh(reel)

    render_reel_task.delay(str(reel.id))

    res = ReelResponse.model_validate(reel)
    if reel.video_key:
        res.video_url = storage_service.generate_presigned_download_url(reel.video_key)
    return res


@router.post("/{id}/render", response_model=ReelResponse)
async def trigger_reel_render(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reel)
        .join(Project)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    reel.render_status = "pending"
    reel.render_progress = 0.0
    await db.commit()

    render_reel_task.delay(str(reel.id))
    return ReelResponse.model_validate(reel)


@router.get("/{id}/download")
async def download_reel(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Reel)
        .join(Project)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    reel = result.scalar_one_or_none()
    if not reel or not reel.video_key:
        raise HTTPException(status_code=404, detail="Reel video not available for download")

    safe_title = "".join(c for c in reel.title if c.isalnum() or c in (" ", "_", "-")).strip() or "reel"
    filename = f"{safe_title[:40]}.mp4"
    url = storage_service.generate_presigned_download_url(reel.video_key, filename=filename)
    return RedirectResponse(url=url)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reel(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a single reel and clean up its storage media and thumbnail.
    """
    result = await db.execute(
        select(Reel)
        .join(Project)
        .where(Reel.id == id, Project.user_id == current_user.id)
    )
    reel = result.scalar_one_or_none()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    # Clean up storage artifacts
    if reel.video_key:
        storage_service.delete_file(reel.video_key)
    if reel.thumbnail_key:
        storage_service.delete_file(reel.thumbnail_key)
    if reel.source_media_key:
        # If this source_media_key is only used by this reel, delete it too
        other_reels = await db.execute(
            select(Reel.id).where(Reel.source_media_key == reel.source_media_key, Reel.id != reel.id)
        )
        if not other_reels.first():
            storage_service.delete_file(reel.source_media_key)

    await db.delete(reel)
    await db.commit()
    return None
