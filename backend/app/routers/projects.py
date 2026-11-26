import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.models.bulk_export import BulkExport
from app.schemas.project import (
    ProjectResponse,
    ProjectListResponse,
    ProjectCreateUrl,
    UrlMetadataResponse,
    ProjectSettingsUpdate,
)
from app.schemas.reel import ReelResponse, ReelListResponse, ManualReelCreate
from app.schemas.bulk_export import BulkExportResponse
from app.services.auth import get_current_user
from app.services.url_importer import fetch_url_metadata, detect_platform
from app.services.storage import storage_service
from app.tasks.pipeline import (
    process_url_import,
    probe_and_prepare_source,
    run_analysis_pipeline,
    render_reel_task,
    process_bulk_zip_export,
)
from app.config import settings

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    query = (
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(desc(Project.created_at))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    response_items = []
    for p in items:
        resp = ProjectResponse.model_validate(p)
        if p.source_file_key:
            resp.source_video_url = storage_service.generate_presigned_download_url(
                p.source_file_key, expires_in=7200
            )
        response_items.append(resp)

    count_query = select(func.count(Project.id)).where(Project.user_id == current_user.id)
    total = (await db.execute(count_query)).scalar() or 0

    return ProjectListResponse(items=response_items, total=total)


@router.post("/metadata", response_model=UrlMetadataResponse)
async def check_url_metadata(
    req: ProjectCreateUrl,
    current_user: User = Depends(get_current_user),
):
    try:
        meta = await fetch_url_metadata(req.url)
        return UrlMetadataResponse(**meta)
    except Exception as e:
        platform = detect_platform(req.url)
        return UrlMetadataResponse(
            url=req.url,
            platform=platform,
            title=None,
            duration=None,
            thumbnail_url=None,
            can_import_media=False,
            message=f"Validation failed: {str(e)}",
        )


@router.post("/url", response_model=ProjectResponse)
async def create_project_from_url(
    req: ProjectCreateUrl,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platform = detect_platform(req.url)
    title = req.title or f"{platform.capitalize()} Import"

    project = Project(
        user_id=current_user.id,
        title=title,
        source_type=platform,
        source_url=req.url,
        status="importing",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Queue background URL download and pipeline
    process_url_import.delay(str(project.id), req.url)

    return project


def validate_project_settings(
    framing_mode: str,
    pan_x_offset: float,
    subtitle_font_size: int,
    split_facecam_crop: Optional[dict],
    split_gameplay_crop: Optional[dict],
    subtitle_position: Optional[str] = None,
    subtitle_y_percent: Optional[float] = None,
    subtitle_color: Optional[str] = None,
    subtitle_font_family: Optional[str] = None,
):
    if framing_mode not in ["crop", "fit", "pan", "split"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid framing mode: '{framing_mode}'. Must be 'crop', 'fit', 'pan', or 'split'.",
        )
    if framing_mode == "pan":
        if pan_x_offset < -1.0 or pan_x_offset > 1.0:
            raise HTTPException(
                status_code=400,
                detail="Pan offset must be between -1.0 and 1.0.",
            )
    if framing_mode == "split":
        for name, crop in [("Facecam", split_facecam_crop), ("Gameplay", split_gameplay_crop)]:
            if not crop or not isinstance(crop, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} crop region is required for Gaming Split Screen. Please frame the {name.lower()} area.",
                )
            x = float(crop.get("x", 0.0))
            y = float(crop.get("y", 0.0))
            w = float(crop.get("width", 0.0))
            h = float(crop.get("height", 0.0))
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} crop coordinates must be normalized between 0.0 and 1.0.",
                )
            if x + w > 1.005 or y + h > 1.005:
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} crop boundaries must stay within the source video bounds.",
                )
    if subtitle_font_size < 30 or subtitle_font_size > 100:
        raise HTTPException(
            status_code=400,
            detail="Subtitle font size must be between 30 and 100 pixels.",
        )
    if subtitle_position is not None and subtitle_position not in ["bottom", "middle", "top"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subtitle position: '{subtitle_position}'. Must be 'bottom', 'middle', or 'top'.",
        )
    if subtitle_y_percent is not None and (subtitle_y_percent < 0.1 or subtitle_y_percent > 0.95):
        raise HTTPException(
            status_code=400,
            detail="Subtitle vertical position must be between 0.10 and 0.95.",
        )


@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    res = ProjectResponse.model_validate(project)
    if project.source_file_key:
        res.source_video_url = storage_service.generate_presigned_download_url(
            project.source_file_key, expires_in=7200
        )
    return res


@router.patch("/{id}/settings", response_model=ProjectResponse)
async def update_project_settings(
    id: uuid.UUID,
    req: ProjectSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if req.framing_mode is not None:
        project.framing_mode = req.framing_mode
    if req.pan_x_offset is not None:
        project.pan_x_offset = max(-1.0, min(1.0, req.pan_x_offset))
    if req.subtitle_font_size is not None:
        project.subtitle_font_size = max(30, min(100, req.subtitle_font_size))
    if req.subtitle_position is not None:
        if req.subtitle_position in ("bottom", "middle", "top"):
            project.subtitle_position = req.subtitle_position
    if req.subtitle_y_percent is not None:
        project.subtitle_y_percent = max(0.1, min(0.95, req.subtitle_y_percent))
    if req.subtitle_color is not None:
        project.subtitle_color = req.subtitle_color
    if req.subtitle_font_family is not None:
        project.subtitle_font_family = req.subtitle_font_family
    if req.split_facecam_crop is not None:
        project.split_facecam_crop = req.split_facecam_crop
    if req.split_gameplay_crop is not None:
        project.split_gameplay_crop = req.split_gameplay_crop
    if req.split_order is not None:
        if req.split_order in ("facecam_top", "gameplay_top"):
            project.split_order = req.split_order
    if req.split_ratio is not None:
        project.split_ratio = max(0.1, min(0.9, req.split_ratio))

    await db.commit()
    await db.refresh(project)

    res = ProjectResponse.model_validate(project)
    if project.source_file_key:
        res.source_video_url = storage_service.generate_presigned_download_url(
            project.source_file_key, expires_in=7200
        )
    return res


@router.post("/{id}/generate", response_model=ProjectResponse)
async def generate_project_reels(
    id: uuid.UUID,
    settings_override: Optional[ProjectSettingsUpdate] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.source_file_key or not project.duration:
        raise HTTPException(
            status_code=400,
            detail="Source media is not available or has not finished probing. Cannot generate reels.",
        )

    # Apply any updated settings if passed with the generate request
    if settings_override:
        if settings_override.framing_mode is not None:
            project.framing_mode = settings_override.framing_mode
        if settings_override.pan_x_offset is not None:
            project.pan_x_offset = max(-1.0, min(1.0, settings_override.pan_x_offset))
        if settings_override.subtitle_font_size is not None:
            project.subtitle_font_size = max(30, min(100, settings_override.subtitle_font_size))
        if settings_override.subtitle_position is not None:
            if settings_override.subtitle_position in ("bottom", "middle", "top"):
                project.subtitle_position = settings_override.subtitle_position
        if settings_override.subtitle_y_percent is not None:
            project.subtitle_y_percent = max(0.1, min(0.95, settings_override.subtitle_y_percent))
        if settings_override.subtitle_color is not None:
            project.subtitle_color = settings_override.subtitle_color
        if settings_override.subtitle_font_family is not None:
            project.subtitle_font_family = settings_override.subtitle_font_family
        if settings_override.split_facecam_crop is not None:
            project.split_facecam_crop = settings_override.split_facecam_crop
        if settings_override.split_gameplay_crop is not None:
            project.split_gameplay_crop = settings_override.split_gameplay_crop
        if settings_override.split_order is not None:
            if settings_override.split_order in ("facecam_top", "gameplay_top"):
                project.split_order = settings_override.split_order
        if settings_override.split_ratio is not None:
            project.split_ratio = max(0.1, min(0.9, settings_override.split_ratio))

    # Backend enforcement: validate required settings before generation
    validate_project_settings(
        framing_mode=project.framing_mode,
        pan_x_offset=project.pan_x_offset,
        subtitle_font_size=project.subtitle_font_size,
        split_facecam_crop=project.split_facecam_crop,
        split_gameplay_crop=project.split_gameplay_crop,
        subtitle_position=project.subtitle_position,
        subtitle_y_percent=project.subtitle_y_percent,
        subtitle_color=project.subtitle_color,
        subtitle_font_family=project.subtitle_font_family,
    )

    # Persist immutable snapshot for this generation job
    project.settings_snapshot = {
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
    project.status = "analyzing"
    project.error_message = None
    await db.commit()
    await db.refresh(project)

    # Launch Celery analysis pipeline
    run_analysis_pipeline.delay(str(project.id))

    res = ProjectResponse.model_validate(project)
    if project.source_file_key:
        res.source_video_url = storage_service.generate_presigned_download_url(
            project.source_file_key, expires_in=7200
        )
    return res


@router.get("/{id}/sample-transcript")
async def get_project_sample_transcript(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.chunk import AnalysisChunk
    chunks_res = await db.execute(
        select(AnalysisChunk).where(
            AnalysisChunk.project_id == id,
            AnalysisChunk.status == "completed",
            AnalysisChunk.transcript.isnot(None),
        ).order_by(AnalysisChunk.chunk_index)
    )
    first_chunk = chunks_res.scalars().first()
    if first_chunk and first_chunk.transcript and len(first_chunk.transcript) > 0:
        words = first_chunk.transcript[:12]
        return {"words": words, "is_mock": False}

    return {
        "words": [
            {"word": "CREATE", "start": 0.0, "end": 0.3},
            {"word": "VIRAL", "start": 0.3, "end": 0.6},
            {"word": "GAMING", "start": 0.6, "end": 0.9},
            {"word": "REELS", "start": 0.9, "end": 1.3},
            {"word": "WITH", "start": 1.3, "end": 1.6},
            {"word": "AUTO", "start": 1.6, "end": 1.9},
            {"word": "SUBTITLES", "start": 1.9, "end": 2.5},
        ],
        "is_mock": True,
    }


@router.post("/{id}/retry")
async def retry_project(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status == "failed" and project.source_file_key:
        if not project.settings_snapshot:
            # Source uploaded/imported but user hasn't generated reels yet: prepare source for Reel Settings
            project.status = "probing"
            project.error_message = None
            await db.commit()
            probe_and_prepare_source.delay(str(project.id))
            return {"status": "retrying_probe"}
        else:
            project.status = "analyzing"
            project.error_message = None
            await db.commit()
            run_analysis_pipeline.delay(str(project.id))
            return {"status": "retrying"}
    elif project.status == "failed" and project.source_url:
        project.status = "importing"
        project.error_message = None
        await db.commit()
        process_url_import.delay(str(project.id), project.source_url)
        return {"status": "retrying_import"}

    return {"status": "not_eligible_for_retry"}


@router.post("/{id}/cancel")
async def cancel_project(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "cancelled"
    await db.commit()
    return {"status": "cancelled"}


@router.get("/{id}/reels", response_model=ReelListResponse)
async def list_project_reels(
    id: uuid.UUID,
    min_score: float = Query(default=60.0, ge=0.0, le=100.0),
    include_borderline: bool = Query(default=False),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_res = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(Reel).where(Reel.project_id == id)
    if not include_borderline:
        query = query.where(Reel.score >= min_score)
    if category and category != "all":
        query = query.where(Reel.category == category)

    query = query.order_by(desc(Reel.score))
    result = await db.execute(query)
    reels = result.scalars().all()

    # Borderline count
    borderline_res = await db.execute(
        select(func.count(Reel.id)).where(Reel.project_id == id, Reel.score < settings.DEFAULT_MIN_SCORE)
    )
    borderline_count = borderline_res.scalar() or 0

    # Attach presigned download and thumbnail URLs
    response_items = []
    for r in reels:
        item = ReelResponse.model_validate(r)
        if r.video_key:
            item.video_url = storage_service.generate_presigned_download_url(r.video_key)
        if r.thumbnail_key:
            item.thumbnail_url = storage_service.generate_presigned_download_url(r.thumbnail_key)
        response_items.append(item)

    return ReelListResponse(
        items=response_items,
        total=len(response_items),
        borderline_count=borderline_count,
    )


@router.post("/{id}/reels/manual", response_model=ReelResponse)
async def create_manual_reel(
    id: uuid.UUID,
    req: ManualReelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_res = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    clip_dur = req.source_end - req.source_start
    if clip_dur < settings.MIN_CLIP_DURATION or clip_dur > settings.MAX_CLIP_DURATION:
        raise HTTPException(
            status_code=400,
            detail=f"Clip duration must be between {settings.MIN_CLIP_DURATION} and {settings.MAX_CLIP_DURATION} seconds. Got {clip_dur:.1f}s.",
        )

    top_cap = (req.top_caption or req.title or "CUSTOM MOMENT").upper()

    reel = Reel(
        project_id=project.id,
        title=top_cap,
        reason="Manually specified timeline clip",
        category="highlight",
        source_start=round(req.source_start, 2),
        source_end=round(req.source_end, 2),
        clip_duration=round(clip_dur, 2),
        score=90.0,
        score_hook=90.0,
        score_payoff=90.0,
        score_clarity=90.0,
        score_entertainment=90.0,
        is_borderline=False,
        framing_mode=req.framing_mode,
        pan_x_offset=req.pan_x_offset,
        split_facecam_crop=req.split_facecam_crop,
        split_gameplay_crop=req.split_gameplay_crop,
        split_order=req.split_order or "facecam_top",
        split_ratio=req.split_ratio or 0.35,
        top_caption=top_cap,
        subtitles_json=[],
        render_status="pending",
    )
    db.add(reel)
    await db.commit()
    await db.refresh(reel)

    # Queue rendering
    render_reel_task.delay(str(reel.id))

    return ReelResponse.model_validate(reel)


@router.post("/{id}/export-zip", response_model=BulkExportResponse)
async def trigger_zip_export(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj_res = await db.execute(
        select(Project).where(Project.id == id, Project.user_id == current_user.id)
    )
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    bulk_export = BulkExport(
        project_id=project.id,
        status="pending",
    )
    db.add(bulk_export)
    await db.commit()
    await db.refresh(bulk_export)

    process_bulk_zip_export.delay(str(bulk_export.id))
    return BulkExportResponse.model_validate(bulk_export)


@router.get("/{id}/export-zip/{export_id}", response_model=BulkExportResponse)
async def get_zip_export_status(
    id: uuid.UUID,
    export_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BulkExport)
        .join(Project)
        .where(
            BulkExport.id == export_id,
            BulkExport.project_id == id,
            Project.user_id == current_user.id,
        )
    )
    export_row = result.scalar_one_or_none()
    if not export_row:
        raise HTTPException(status_code=404, detail="Export not found")

    res = BulkExportResponse.model_validate(export_row)
    if export_row.status == "completed" and export_row.zip_key:
        res.download_url = storage_service.generate_presigned_download_url(
            export_row.zip_key, filename="reels_collection.zip"
        )
    return res


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Project)
        .options(
            selectinload(Project.reels),
            selectinload(Project.bulk_exports),
            selectinload(Project.live_session),
        )
        .where(Project.id == id, Project.user_id == current_user.id)
    )
    res = await db.execute(query)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete storage files for reels
    for reel in project.reels:
        for k in [reel.video_key, reel.thumbnail_key, reel.source_media_key]:
            if k:
                storage_service.delete_file(k)

    # Delete storage files for bulk exports
    for exp in project.bulk_exports:
        if exp.zip_key:
            storage_service.delete_file(exp.zip_key)

    # Delete project source file & live preview
    if project.source_file_key:
        storage_service.delete_file(project.source_file_key)
    if project.live_session and project.live_session.preview_frame_key:
        storage_service.delete_file(project.live_session.preview_frame_key)

    # Delete any prefix objects for project
    storage_service.delete_prefix(f"projects/{id}/")
    storage_service.delete_prefix(f"live_segments/{id}/")

    # Delete from DB (cascades to reels, chunks, uploads, bulk_exports, live_session)
    await db.delete(project)
    await db.commit()
    return None

