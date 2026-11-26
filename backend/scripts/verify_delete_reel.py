import asyncio
import os
import uuid
import sys
import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.services.storage import storage_service


async def verify_delete_reel():
    print("=" * 60)
    print("VERIFYING REEL DELETION")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User))
        user = user_res.scalars().first()
        if not user:
            print("  ✗ No test user found.")
            sys.exit(1)

        # 1. Create a project
        proj = Project(
            user_id=user.id,
            title="Test Project for Reel Deletion",
            source_type="upload",
            source_file_key="test_media/test_12min.mp4",
            duration=120.0,
            status="completed",
        )
        session.add(proj)
        await session.commit()
        await session.refresh(proj)

        # 2. Upload dummy files for reel
        reel_id = uuid.uuid4()
        video_key = f"projects/{proj.id}/reels/{reel_id}.mp4"
        thumb_key = f"projects/{proj.id}/reels/{reel_id}_thumb.jpg"
        source_clip_key = f"projects/{proj.id}/reels/{reel_id}_source.mp4"

        # Create dummy local files and upload
        dummy_local = "/tmp/dummy_reel_data.bin"
        with open(dummy_local, "wb") as f:
            f.write(b"dummy video data for deletion test")

        storage_service.upload_file(dummy_local, video_key, content_type="video/mp4")
        storage_service.upload_file(dummy_local, thumb_key, content_type="image/jpeg")
        storage_service.upload_file(dummy_local, source_clip_key, content_type="video/mp4")

        assert storage_service.object_exists(video_key), "Failed to upload test video"
        assert storage_service.object_exists(thumb_key), "Failed to upload test thumb"
        assert storage_service.object_exists(source_clip_key), "Failed to upload test source clip"
        print("  ✓ Created test artifacts in MinIO storage.")

        # 3. Create Reel record
        test_reel = Reel(
            id=reel_id,
            project_id=proj.id,
            title="Reel To Be Deleted",
            top_caption="Reel To Be Deleted",
            reason="Testing user deletion",
            source_start=10.0,
            source_end=40.0,
            clip_duration=30.0,
            video_key=video_key,
            thumbnail_key=thumb_key,
            source_media_key=source_clip_key,
            render_status="completed",
        )
        session.add(test_reel)
        await session.commit()
        print(f"  ✓ Created test reel {reel_id} in database.")

    # 4. Call DELETE /api/reels/{id} via HTTP client
    async with httpx.AsyncClient(base_url="http://api:8000") as client:
        # Delete reel
        del_res = await client.delete(f"/api/reels/{reel_id}")
        assert del_res.status_code == 204, f"Expected 204, got {del_res.status_code}: {del_res.text}"
        print("  ✓ DELETE /api/reels/{id} returned HTTP 204 No Content.")

        # Verify GET returns 404
        get_res = await client.get(f"/api/reels/{reel_id}")
        assert get_res.status_code == 404, f"Expected 404, got {get_res.status_code}"
        print("  ✓ GET /api/reels/{id} verified reel no longer exists in DB (HTTP 404).")

        # Verify second DELETE returns 404
        del_again = await client.delete(f"/api/reels/{reel_id}")
        assert del_again.status_code == 404, f"Expected 404 on already deleted reel, got {del_again.status_code}"
        print("  ✓ Repeated DELETE /api/reels/{id} correctly returns 404.")

    # 5. Verify storage cleanup
    assert not storage_service.object_exists(video_key), "Rendered video was not deleted from MinIO!"
    assert not storage_service.object_exists(thumb_key), "Thumbnail was not deleted from MinIO!"
    assert not storage_service.object_exists(source_clip_key), "Source clip was not deleted from MinIO!"
    print("  ✓ MinIO objects verified deleted and purged.")

    print("=" * 60)
    print("REEL DELETION VERIFICATION PASSED WITH 100% SUCCESS!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_delete_reel())
