import math
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.upload import UploadSession
from app.schemas.upload import (
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignedPartUrlResponse,
    CompleteUploadRequest,
    UploadSessionResponse,
    PartETag,
)
from app.services.auth import get_current_user
from app.services.storage import storage_service
from app.tasks.pipeline import run_analysis_pipeline, probe_and_prepare_source

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/initiate", response_model=InitiateUploadResponse)
async def initiate_upload(
    req: InitiateUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = None
    if req.project_id:
        result = await db.execute(
            select(Project).where(
                Project.id == req.project_id, Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    if not project:
        project_title = req.file_name.rsplit(".", 1)[0]
        project = Project(
            user_id=current_user.id,
            title=project_title,
            source_type="upload",
            source_file_size=req.file_size,
            status="created",
        )
        db.add(project)
        await db.flush()

    # Check for existing resumable session with same file and size
    session_result = await db.execute(
        select(UploadSession).where(
            UploadSession.project_id == project.id,
            UploadSession.user_id == current_user.id,
            UploadSession.file_name == req.file_name,
            UploadSession.file_size == req.file_size,
            UploadSession.status == "in_progress",
        )
    )
    existing_session = session_result.scalar_one_or_none()
    if existing_session:
        return InitiateUploadResponse(
            upload_session_id=existing_session.id,
            project_id=project.id,
            upload_id=existing_session.upload_id,
            file_key=existing_session.file_key,
            total_parts=existing_session.total_parts,
            chunk_size=existing_session.chunk_size,
            completed_parts=[PartETag(**p) for p in existing_session.completed_parts],
        )

    # Initialize new S3 multipart upload
    total_parts = math.ceil(req.file_size / req.chunk_size)
    if total_parts <= 0:
        total_parts = 1

    file_key = f"projects/{project.id}/{uuid.uuid4()}_{req.file_name}"
    upload_id = storage_service.create_multipart_upload(file_key, content_type="video/mp4")

    session = UploadSession(
        project_id=project.id,
        user_id=current_user.id,
        upload_id=upload_id,
        file_key=file_key,
        file_name=req.file_name,
        file_size=req.file_size,
        chunk_size=req.chunk_size,
        total_parts=total_parts,
        completed_parts=[],
        status="in_progress",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return InitiateUploadResponse(
        upload_session_id=session.id,
        project_id=project.id,
        upload_id=upload_id,
        file_key=file_key,
        total_parts=total_parts,
        chunk_size=req.chunk_size,
        completed_parts=[],
    )


@router.get("/{session_id}/parts/{part_number}", response_model=PresignedPartUrlResponse)
async def get_part_presigned_url(
    session_id: uuid.UUID,
    part_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.id == session_id, UploadSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session or session.status != "in_progress":
        raise HTTPException(status_code=404, detail="Active upload session not found")

    if part_number < 1 or part_number > session.total_parts:
        raise HTTPException(status_code=400, detail="Invalid part number")

    presigned_url = storage_service.generate_presigned_part_url(
        file_key=session.file_key,
        upload_id=session.upload_id,
        part_number=part_number,
    )

    return PresignedPartUrlResponse(part_number=part_number, presigned_url=presigned_url)


@router.post("/{session_id}/complete")
async def complete_upload(
    session_id: uuid.UUID,
    req: CompleteUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.id == session_id, UploadSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")

    parts_dict_list = [{"PartNumber": p.PartNumber, "ETag": p.ETag} for p in req.parts]

    try:
        storage_service.complete_multipart_upload(
            file_key=session.file_key,
            upload_id=session.upload_id,
            parts=parts_dict_list,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete S3 multipart upload: {str(e)}")

    session.status = "completed"
    session.completed_parts = parts_dict_list

    # Update Project
    proj_result = await db.execute(select(Project).where(Project.id == session.project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        project.source_file_key = session.file_key
        project.source_file_size = session.file_size
        project.status = "probing"

    await db.commit()

    # Trigger source probing and preparation for Reel Settings configuration
    probe_and_prepare_source.delay(str(project.id))

    return {"status": "success", "project_id": str(project.id), "file_key": session.file_key}


@router.get("/{session_id}", response_model=UploadSessionResponse)
async def get_upload_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UploadSession).where(
            UploadSession.id == session_id, UploadSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return session
