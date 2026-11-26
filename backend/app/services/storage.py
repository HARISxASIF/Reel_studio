import os
import time
import threading
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        protocol = "https" if settings.MINIO_SECURE else "http"
        self.endpoint_url = f"{protocol}://{settings.MINIO_ENDPOINT}"
        self.public_endpoint_url = f"{protocol}://{settings.MINIO_PUBLIC_ENDPOINT}"
        self.bucket_name = settings.MINIO_BUCKET

        # Internal client for worker / backend direct access
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=60,
                read_timeout=1200,
                retries={"max_attempts": 10},
            ),
            region_name="us-east-1",
        )

        # Public client for generating presigned URLs reachable by browser
        self.public_s3_client = boto3.client(
            "s3",
            endpoint_url=self.public_endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )

        # In-memory cache for presigned URLs so rapid polling doesn't invalidate media playback
        self._url_cache: Dict[str, Tuple[str, float]] = {}
        self._cache_lock = threading.Lock()

    def ensure_bucket_and_cors(self):
        """Ensure MinIO bucket exists and configure CORS for browser uploads."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' already exists.")
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' created successfully.")
            except Exception as e:
                logger.error(f"Failed to create bucket: {e}")

        # Set CORS policy so browser can upload multipart chunks directly
        cors_configuration = {
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                    "AllowedOrigins": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        }
        try:
            self.s3_client.put_bucket_cors(
                Bucket=self.bucket_name, CORSConfiguration=cors_configuration
            )
            logger.info("CORS configuration set successfully on bucket.")
        except Exception as e:
            logger.warning(f"Could not set CORS configuration: {e}")

    def create_multipart_upload(self, file_key: str, content_type: str = "video/mp4") -> str:
        """Create a multipart upload session in MinIO."""
        response = self.s3_client.create_multipart_upload(
            Bucket=self.bucket_name,
            Key=file_key,
            ContentType=content_type,
        )
        return response["UploadId"]

    def generate_presigned_part_url(
        self, file_key: str, upload_id: str, part_number: int, expires_in: int = 3600
    ) -> str:
        """Generate a presigned PUT URL for uploading a single part directly from the browser."""
        url = self.public_s3_client.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": self.bucket_name,
                "Key": file_key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires_in,
        )
        return url

    def complete_multipart_upload(
        self, file_key: str, upload_id: str, parts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Complete a multipart upload with sorted parts."""
        sorted_parts = sorted(parts, key=lambda p: p["PartNumber"])
        return self.s3_client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=file_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": sorted_parts},
        )

    def abort_multipart_upload(self, file_key: str, upload_id: str):
        """Abort a multipart upload session."""
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=file_key,
                UploadId=upload_id,
            )
        except Exception as e:
            logger.warning(f"Failed to abort multipart upload {upload_id}: {e}")

    def generate_presigned_download_url(
        self, file_key: str, expires_in: int = 7200, filename: Optional[str] = None
    ) -> str:
        """Generate a presigned GET URL for downloading media directly from browser with stable caching."""
        cache_key = f"{file_key}:{filename or ''}"
        now = time.time()

        with self._cache_lock:
            if cache_key in self._url_cache:
                cached_url, exp_time = self._url_cache[cache_key]
                # Reuse cached URL if it still has at least 15 minutes of validity left
                if exp_time - now > 900:
                    return cached_url

        params = {"Bucket": self.bucket_name, "Key": file_key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        url = self.public_s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

        with self._cache_lock:
            self._url_cache[cache_key] = (url, now + expires_in)

        return url

    def get_local_path(self, file_key: str) -> Optional[str]:
        """Check if direct filesystem access to MinIO storage volume is available."""
        candidate = os.path.join("/data", self.bucket_name, file_key)
        if os.path.exists(candidate):
            return candidate
        return None

    def upload_file(self, local_path: str, file_key: str, content_type: Optional[str] = None):
        """Upload a local file directly into MinIO or local volume."""
        direct_target = os.path.join("/data", self.bucket_name, file_key)
        if os.path.isdir("/data"):
            try:
                os.makedirs(os.path.dirname(os.path.abspath(direct_target)), exist_ok=True)
                import shutil
                if os.path.abspath(local_path) != os.path.abspath(direct_target):
                    shutil.copyfile(local_path, direct_target)
                return
            except Exception as e:
                logger.warning(f"Direct volume write to {direct_target} failed, falling back to S3 upload: {e}")

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        transfer_config = TransferConfig(
            multipart_threshold=32 * 1024 * 1024,
            multipart_chunksize=32 * 1024 * 1024,
            max_concurrency=1,
            use_threads=False,
        )
        self.s3_client.upload_file(
            local_path,
            self.bucket_name,
            file_key,
            ExtraArgs=extra_args,
            Config=transfer_config,
        )

    def download_file(self, file_key: str, local_path: str):
        """Download an object from MinIO to a local path, or copy/symlink if local volume mounted."""
        local_direct = self.get_local_path(file_key)
        if local_direct and os.path.exists(local_direct):
            if os.path.abspath(local_direct) == os.path.abspath(local_path):
                return
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            import shutil
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
                os.link(local_direct, local_path)
                return
            except Exception:
                shutil.copyfile(local_direct, local_path)
                return

        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        transfer_config = TransferConfig(
            multipart_threshold=32 * 1024 * 1024,
            multipart_chunksize=32 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True,
        )
        self.s3_client.download_file(self.bucket_name, file_key, local_path, Config=transfer_config)

    def get_object_size(self, file_key: str) -> int:
        """Get object size in bytes."""
        local_direct = self.get_local_path(file_key)
        if local_direct and os.path.exists(local_direct):
            return os.path.getsize(local_direct)
        res = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
        return res.get("ContentLength", 0)

    def object_exists(self, file_key: str) -> bool:
        """Check if an object exists."""
        local_direct = self.get_local_path(file_key)
        if local_direct and os.path.exists(local_direct):
            return True
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError:
            return False

    def delete_file(self, file_key: str):
        """Delete an object from MinIO."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"Deleted storage object: {file_key}")
        except Exception as e:
            logger.warning(f"Failed to delete object {file_key}: {e}")

    def delete_prefix(self, prefix: str):
        """Delete all objects under a prefix from MinIO."""
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if "Contents" in page:
                    delete_keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
                    if delete_keys:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket_name, Delete={"Objects": delete_keys}
                        )
            logger.info(f"Deleted storage prefix: {prefix}")
        except Exception as e:
            logger.warning(f"Failed to delete prefix {prefix}: {e}")


storage_service = StorageService()

