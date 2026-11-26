import os
import time
import uuid
import logging
import requests
from typing import Dict, Any, Optional, Callable
from app.config import settings
from app.services.encryption import decrypt_token
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class PublishingError(Exception):
    def __init__(self, message: str, is_retryable: bool = False, requires_reconnect: bool = False):
        super().__init__(message)
        self.message = message
        self.is_retryable = is_retryable
        self.requires_reconnect = requires_reconnect


def format_combined_caption(
    title: str,
    description: Optional[str] = None,
    hashtags: Optional[list] = None,
    max_length: int = 2200,
) -> str:
    """
    Format a clean combined caption from title (hook), description, and hashtags.
    Respects maximum character limits.
    """
    parts = []
    if title and title.strip():
        parts.append(title.strip())
    if description and description.strip():
        parts.append(description.strip())
    if hashtags:
        clean_tags = []
        for tag in hashtags:
            t = str(tag).strip()
            if not t.startswith("#"):
                t = f"#{t}"
            if t not in clean_tags:
                clean_tags.append(t)
        if clean_tags:
            parts.append(" ".join(clean_tags))

    combined = "\n\n".join(parts)
    if len(combined) > max_length:
        combined = combined[: max_length - 3] + "..."
    return combined


def get_reel_video_filepath(reel, post=None) -> str:
    """Resolve local path or download to temporary file for upload."""
    video_key = (post and post.video_key_snapshot) or reel.video_key
    if not video_key:
        raise PublishingError("Reel does not have a rendered video key")

    local_path = storage_service.get_local_path(video_key)
    if local_path and os.path.exists(local_path):
        return local_path

    # Download to temp file
    temp_dir = "/tmp/reelstudio_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_target = os.path.join(temp_dir, f"{reel.id}_{os.path.basename(video_key)}")
    storage_service.download_file(video_key, temp_target)
    return temp_target


def publish_youtube_short(
    account,
    post,
    video_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Publish vertical video to YouTube Shorts using official resumable upload protocol.
    """
    opts = post.platform_options or {}
    visibility = opts.get("visibility", "public")  # public, unlisted, private
    made_for_kids = bool(opts.get("made_for_kids", False))

    # Format YouTube title (max 100 chars) & description
    title = (post.post_title or "Reel").strip()
    if len(title) > 95:
        title = title[:92] + "..."
    # Append #Shorts to ensure YouTube categorizes as a short
    if "#Shorts" not in title and len(title) + 8 <= 100:
        title = f"{title} #Shorts"

    description = format_combined_caption(
        title="",
        description=post.post_description,
        hashtags=post.post_hashtags or ["#Shorts", "#Gaming"],
        max_length=5000,
    )

    if account.is_mock or not account.access_token_encrypted:
        logger.info(f"[MOCK] Simulating YouTube Shorts publish for post {post.id}...")
        for p in [20, 50, 80, 100]:
            if progress_callback:
                progress_callback(p, "uploading" if p < 100 else "published")
            time.sleep(0.3)
        mock_id = f"yt_{uuid.uuid4().hex[:11]}"
        return {
            "provider_post_id": mock_id,
            "provider_post_url": f"https://www.youtube.com/shorts/{mock_id}",
            "provider_upload_id": f"upl_{uuid.uuid4().hex[:8]}",
            "visibility": visibility,
        }

    # Real YouTube Data API Resumable Upload
    access_token = decrypt_token(account.access_token_encrypted)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
    }
    file_size = os.path.getsize(video_path)
    headers["X-Upload-Content-Length"] = str(file_size)

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [t.replace("#", "") for t in (post.post_hashtags or [])],
            "categoryId": "20",  # Gaming
        },
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": made_for_kids,
            "embeddable": True,
        },
    }

    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    init_res = requests.post(init_url, headers=headers, json=metadata, timeout=30)

    if init_res.status_code == 401:
        # Attempt to refresh token using owner's OAuth Client ID and Secret
        refreshed = False
        if account.refresh_token_encrypted:
            try:
                from app.database import SyncSessionLocal
                from app.models.user_credential import UserCredential
                from app.services.encryption import encrypt_token
                sync_db = SyncSessionLocal()
                try:
                    c_row = sync_db.query(UserCredential).filter(UserCredential.user_id == account.user_id).first()
                    client_id = (c_row and c_row.youtube_client_id) or settings.YOUTUBE_CLIENT_ID
                    client_secret = None
                    if c_row and c_row.youtube_client_secret_encrypted:
                        client_secret = decrypt_token(c_row.youtube_client_secret_encrypted)
                    if not client_secret:
                        client_secret = settings.YOUTUBE_CLIENT_SECRET

                    ref_tok = decrypt_token(account.refresh_token_encrypted)
                    if client_id and client_secret and ref_tok:
                        token_res = requests.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "refresh_token": ref_tok,
                                "grant_type": "refresh_token",
                            },
                            timeout=30,
                        )
                        if token_res.status_code == 200:
                            new_data = token_res.json()
                            new_access = new_data.get("access_token")
                            if new_access:
                                access_token = new_access
                                headers["Authorization"] = f"Bearer {access_token}"
                                init_res = requests.post(init_url, headers=headers, json=metadata, timeout=30)
                                if init_res.status_code in (200, 201):
                                    refreshed = True
                                    from app.models.social import SocialAccount
                                    acc_row = sync_db.query(SocialAccount).filter(SocialAccount.id == account.id).first()
                                    if acc_row:
                                        acc_row.access_token_encrypted = encrypt_token(new_access)
                                        sync_db.commit()
                finally:
                    sync_db.close()
            except Exception as refr_err:
                logger.warning(f"YouTube token refresh failed: {refr_err}")

        if not refreshed and init_res.status_code == 401:
            raise PublishingError("YouTube token expired or invalid", requires_reconnect=True)
    if init_res.status_code not in (200, 201):
        raise PublishingError(f"YouTube upload init failed: {init_res.text}", is_retryable=True)

    upload_location = init_res.headers.get("Location")
    if not upload_location:
        raise PublishingError("YouTube did not return resumable upload Location header")

    if progress_callback:
        progress_callback(30, "uploading")

    # Stream upload in 10MB chunks
    chunk_size = 10 * 1024 * 1024
    with open(video_path, "rb") as f:
        offset = 0
        while offset < file_size:
            chunk = f.read(chunk_size)
            length = len(chunk)
            chunk_headers = {
                "Content-Range": f"bytes {offset}-{offset + length - 1}/{file_size}",
                "Content-Length": str(length),
                "Content-Type": "video/mp4",
            }
            res = requests.put(upload_location, headers=chunk_headers, data=chunk, timeout=120)
            offset += length
            pct = int((offset / file_size) * 70) + 30
            if progress_callback:
                progress_callback(min(pct, 95), "uploading")

    if res.status_code not in (200, 201):
        raise PublishingError(f"YouTube upload transfer failed: {res.text}", is_retryable=True)

    video_data = res.json()
    video_id = video_data.get("id")
    return {
        "provider_post_id": video_id,
        "provider_post_url": f"https://www.youtube.com/shorts/{video_id}",
        "provider_upload_id": upload_location,
        "visibility": visibility,
    }


def publish_facebook_page_reel(
    account,
    post,
    video_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Publish reel to a Facebook Page using the official Meta Page Reels Publishing API.
    Flow: 1) Start upload session -> 2) Upload video binary -> 3) Finish & publish reel.
    """
    caption = format_combined_caption(
        title=post.post_title,
        description=post.post_description,
        hashtags=post.post_hashtags,
        max_length=5000,
    )
    meta = account.metadata_json or {}
    page_id = (post.platform_options or {}).get("page_id") or meta.get("page_id") or account.platform_account_id

    if account.is_mock or not account.access_token_encrypted:
        logger.info(f"[MOCK] Simulating Facebook Page Reel publish for post {post.id}...")
        for p in [25, 60, 85, 100]:
            if progress_callback:
                progress_callback(p, "uploading" if p < 100 else "published")
            time.sleep(0.3)
        mock_id = f"fb_reel_{uuid.uuid4().hex[:12]}"
        return {
            "provider_post_id": mock_id,
            "provider_post_url": f"https://www.facebook.com/reel/{mock_id}",
            "provider_upload_id": f"fb_upl_{uuid.uuid4().hex[:8]}",
        }

    access_token = decrypt_token(account.access_token_encrypted)

    # Step 1: Initialize session
    init_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    init_res = requests.post(
        init_url,
        params={"access_token": access_token, "upload_phase": "start"},
        timeout=30,
    )
    if init_res.status_code == 401 or "OAuthException" in init_res.text:
        raise PublishingError("Facebook Page token invalid or expired", requires_reconnect=True)
    if init_res.status_code != 200:
        raise PublishingError(f"Facebook Reels init failed: {init_res.text}", is_retryable=True)

    session_data = init_res.json()
    video_id = session_data.get("video_id")
    upload_url = session_data.get("upload_url")

    if progress_callback:
        progress_callback(25, "uploading")

    # Step 2: Transfer binary chunk
    file_size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        file_bytes = f.read()

    upload_headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }
    up_res = requests.post(upload_url, headers=upload_headers, data=file_bytes, timeout=180)
    if up_res.status_code != 200:
        raise PublishingError(f"Facebook Reels binary upload failed: {up_res.text}", is_retryable=True)

    if progress_callback:
        progress_callback(75, "processing")

    # Step 3: Finish and publish
    finish_res = requests.post(
        init_url,
        params={
            "access_token": access_token,
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
        },
        timeout=30,
    )
    if finish_res.status_code != 200:
        raise PublishingError(f"Facebook Reels finish failed: {finish_res.text}", is_retryable=True)

    return {
        "provider_post_id": video_id,
        "provider_post_url": f"https://www.facebook.com/reel/{video_id}",
        "provider_upload_id": upload_url,
    }


def publish_instagram_reel(
    account,
    post,
    video_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Publish reel to Instagram Professional/Creator account via Meta Graph API.
    Flow: 1) Container creation -> 2) Wait for ready -> 3) Publish container -> 4) Get permalink.
    """
    caption = format_combined_caption(
        title=post.post_title,
        description=post.post_description,
        hashtags=post.post_hashtags,
        max_length=2200,
    )
    share_to_feed = (post.platform_options or {}).get("share_to_feed", True)
    ig_user_id = account.platform_account_id

    if account.is_mock or not account.access_token_encrypted:
        logger.info(f"[MOCK] Simulating Instagram Reel publish for post {post.id}...")
        for p in [25, 55, 80, 100]:
            if progress_callback:
                progress_callback(p, "uploading" if p < 80 else "published")
            time.sleep(0.3)
        mock_code = f"C{uuid.uuid4().hex[:9]}"
        return {
            "provider_post_id": f"ig_{uuid.uuid4().hex[:12]}",
            "provider_post_url": f"https://www.instagram.com/reel/{mock_code}/",
            "provider_upload_id": f"ig_cnt_{uuid.uuid4().hex[:8]}",
        }

    # Meta Instagram Reels API requires an externally reachable HTTPS video URL
    public_video_url = post.rendered_video_url
    if not public_video_url or "localhost" in public_video_url:
        # Check if MinIO public URL or cloud endpoint is reachable
        video_key = post.video_key_snapshot or (post.reel and post.reel.video_key)
        if video_key:
            public_video_url = storage_service.generate_presigned_download_url(video_key, expires_in=7200)

    if not public_video_url or "localhost" in public_video_url:
        raise PublishingError(
            "Instagram publishing requires a public internet-accessible HTTPS video URL so Meta can fetch the media. "
            "Localhost URLs are not reachable by Meta. Use Mock Mode or deploy Reel Studio with a public domain or tunnel (ngrok).",
            is_retryable=False,
        )

    access_token = decrypt_token(account.access_token_encrypted)

    # Step 1: Create Reel Container
    container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    container_params = {
        "access_token": access_token,
        "media_type": "REELS",
        "video_url": public_video_url,
        "caption": caption,
        "share_to_feed": str(share_to_feed).lower(),
    }
    c_res = requests.post(container_url, data=container_params, timeout=30)
    if c_res.status_code == 401 or "OAuthException" in c_res.text:
        raise PublishingError("Instagram token invalid or expired", requires_reconnect=True)
    if c_res.status_code != 200:
        raise PublishingError(f"Instagram container creation failed: {c_res.text}", is_retryable=True)

    creation_id = c_res.json().get("id")

    if progress_callback:
        progress_callback(40, "processing")

    # Step 2: Poll container status until FINISHED
    status_url = f"https://graph.facebook.com/v19.0/{creation_id}"
    ready = False
    for _ in range(30):  # Wait up to 2.5 minutes
        time.sleep(5)
        st_res = requests.get(status_url, params={"access_token": access_token, "fields": "status_code"}, timeout=15)
        if st_res.status_code == 200:
            status_code = st_res.json().get("status_code")
            if status_code == "FINISHED":
                ready = True
                break
            elif status_code == "ERROR":
                raise PublishingError(f"Instagram media processing failed: {st_res.text}")
        if progress_callback:
            progress_callback(60, "processing")

    if not ready:
        raise PublishingError("Instagram media container processing timed out", is_retryable=True)

    if progress_callback:
        progress_callback(80, "uploading")

    # Step 3: Publish container
    pub_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    pub_res = requests.post(
        pub_url,
        data={"access_token": access_token, "creation_id": creation_id},
        timeout=30,
    )
    if pub_res.status_code != 200:
        raise PublishingError(f"Instagram publish failed: {pub_res.text}", is_retryable=True)

    media_id = pub_res.json().get("id")

    # Step 4: Fetch permalink
    permalink = f"https://www.instagram.com/p/{media_id}/"
    try:
        info_res = requests.get(
            f"https://graph.facebook.com/v19.0/{media_id}",
            params={"access_token": access_token, "fields": "permalink"},
            timeout=15,
        )
        if info_res.status_code == 200 and "permalink" in info_res.json():
            permalink = info_res.json()["permalink"]
    except Exception:
        pass

    return {
        "provider_post_id": media_id,
        "provider_post_url": permalink,
        "provider_upload_id": creation_id,
    }


def publish_tiktok_video(
    account,
    post,
    video_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Publish video to TikTok using TikTok Direct Post API v2.
    """
    caption = format_combined_caption(
        title=post.post_title,
        description=post.post_description,
        hashtags=post.post_hashtags,
        max_length=2200,
    )
    opts = post.platform_options or {}
    privacy_level = opts.get("privacy_level", "PUBLIC_TO_EVERYONE")
    disable_duet = opts.get("disable_duet", False)
    disable_stitch = opts.get("disable_stitch", False)
    disable_comment = opts.get("disable_comment", False)

    if account.is_mock or not account.access_token_encrypted:
        logger.info(f"[MOCK] Simulating TikTok publish for post {post.id}...")
        for p in [20, 50, 75, 100]:
            if progress_callback:
                progress_callback(p, "uploading" if p < 100 else "published")
            time.sleep(0.3)
        mock_id = f"7{uuid.uuid4().hex[:18]}"
        user_handle = account.account_username or "user"
        return {
            "provider_post_id": mock_id,
            "provider_post_url": f"https://www.tiktok.com/@{user_handle}/video/{mock_id}",
            "provider_upload_id": f"tt_upl_{uuid.uuid4().hex[:8]}",
        }

    access_token = decrypt_token(account.access_token_encrypted)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    file_size = os.path.getsize(video_path)

    init_payload = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_stitch": disable_stitch,
            "disable_comment": disable_comment,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    init_res = requests.post(init_url, headers=headers, json=init_payload, timeout=30)

    if init_res.status_code == 401:
        raise PublishingError("TikTok token invalid or expired", requires_reconnect=True)
    if init_res.status_code != 200:
        raise PublishingError(f"TikTok init failed: {init_res.text}", is_retryable=True)

    data = init_res.json().get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")

    if progress_callback:
        progress_callback(30, "uploading")

    # Upload video
    with open(video_path, "rb") as f:
        file_bytes = f.read()

    put_headers = {
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        "Content-Type": "video/mp4",
    }
    put_res = requests.put(upload_url, headers=put_headers, data=file_bytes, timeout=180)
    if put_res.status_code not in (200, 201):
        raise PublishingError(f"TikTok video upload failed: {put_res.text}", is_retryable=True)

    if progress_callback:
        progress_callback(80, "processing")

    user_handle = account.account_username or "user"
    return {
        "provider_post_id": publish_id,
        "provider_post_url": f"https://www.tiktok.com/@{user_handle}",
        "provider_upload_id": upload_url,
    }


def publish_post_to_destination(
    account,
    post,
    reel,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Main dispatcher that publishes a post to its corresponding platform.
    """
    if account.status == "disconnected" or not account.is_active:
        raise PublishingError("Connected social account has been disconnected or deactivated", requires_reconnect=True)

    video_path = get_reel_video_filepath(reel, post)

    platform = account.platform.lower()
    if platform == "youtube":
        return publish_youtube_short(account, post, video_path, progress_callback)
    elif platform == "facebook":
        return publish_facebook_page_reel(account, post, video_path, progress_callback)
    elif platform == "instagram":
        return publish_instagram_reel(account, post, video_path, progress_callback)
    elif platform == "tiktok":
        return publish_tiktok_video(account, post, video_path, progress_callback)
    else:
        raise PublishingError(f"Unsupported destination platform: {platform}")
