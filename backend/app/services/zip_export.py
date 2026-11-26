import os
import zipfile
import tempfile
import logging
from typing import List
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


def create_reels_zip_archive(
    reel_items: List[dict],
    zip_output_key: str,
    project_title: str,
) -> str:
    """
    Downloads completed reel MP4s and bundles them into a ZIP archive without holding in memory.
    Uploads result to MinIO under zip_output_key.
    Returns zip_output_key.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, f"{project_title[:30]}_reels.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, reel in enumerate(reel_items, start=1):
                video_key = reel.get("video_key")
                if not video_key:
                    continue

                safe_title = "".join(c for c in reel.get("title", f"Reel_{idx}") if c.isalnum() or c in (" ", "_", "-")).rstrip()
                reel_filename = f"{idx:02d}_{safe_title[:40]}.mp4"
                tmp_reel_path = os.path.join(tmp_dir, f"reel_{idx}.mp4")

                try:
                    storage_service.download_file(video_key, tmp_reel_path)
                    zipf.write(tmp_reel_path, arcname=reel_filename)
                except Exception as e:
                    logger.error(f"Failed to add reel {video_key} to zip: {e}")
                finally:
                    if os.path.exists(tmp_reel_path):
                        os.remove(tmp_reel_path)

        storage_service.upload_file(zip_path, zip_output_key, content_type="application/zip")
        return zip_output_key
