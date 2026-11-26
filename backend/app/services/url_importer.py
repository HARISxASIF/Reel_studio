import os
import re
import socket
import ipaddress
import urllib.parse
import httpx
import logging
from typing import Dict, Any, Optional, Tuple
import yt_dlp
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

# SSRF Protection: Deny private, loopback, link-local, and reserved IP ranges
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_ip_allowed(ip_str: str) -> bool:
    """Check if an IP address is public and safe to access."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
        for net in BLOCKED_NETWORKS:
            if ip in net:
                return False
        return True
    except ValueError:
        return False


def validate_url_security(url: str, allow_local: Optional[bool] = None) -> str:
    """
    Validate that the URL uses HTTP/HTTPS and resolves to a public, non-private IP address.
    Raises ValueError on SSRF / unsafe attempts.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL hostname is missing.")

    from app.config import settings
    permit_local = allow_local if allow_local is not None else settings.ALLOW_LOCAL_FEEDS
    if permit_local:
        return url

    # Disallow localhost keywords
    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "minio", "postgres", "redis", "api", "web"):
        raise ValueError("Access to local network hosts is strictly prohibited.")

    # Resolve IP addresses for hostname
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for item in addr_info:
            ip = item[4][0]
            if not is_ip_allowed(ip):
                raise ValueError(f"URL resolves to restricted IP address: {ip}")
    except socket.gaierror as e:
        raise ValueError(f"Failed to resolve hostname '{hostname}': {e}")

    return url


def detect_platform(url: str) -> str:
    """Detect source platform from URL."""
    lowered = url.lower()
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return "youtube"
    elif "twitch.tv" in lowered:
        return "twitch"
    elif "kick.com" in lowered:
        return "kick"
    elif any(lowered.endswith(ext) for ext in [".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"]):
        return "direct_url"
    else:
        return "direct_url"


async def fetch_url_metadata(url: str) -> Dict[str, Any]:
    """
    Probe URL metadata safely and determine if media import is possible.
    """
    validate_url_security(url)
    platform = detect_platform(url)

    if platform == "direct_url":
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Check redirect destination for SSRF safety as well
            try:
                res = await client.head(url)
                final_url = str(res.url)
                validate_url_security(final_url)
                content_type = res.headers.get("content-type", "")
                content_length = res.headers.get("content-length")
                is_video = "video" in content_type or any(url.lower().endswith(ext) for ext in [".mp4", ".mkv", ".webm", ".mov"])

                return {
                    "url": url,
                    "platform": "direct_url",
                    "title": os.path.basename(urllib.parse.urlparse(url).path) or "Direct Video Stream",
                    "duration": None,
                    "thumbnail_url": None,
                    "can_import_media": is_video,
                    "message": "Direct media file available for streaming download." if is_video else "URL does not appear to return a direct video stream. You can upload the original file.",
                }
            except Exception as e:
                return {
                    "url": url,
                    "platform": "direct_url",
                    "title": os.path.basename(urllib.parse.urlparse(url).path) or "Direct Video",
                    "duration": None,
                    "thumbnail_url": None,
                    "can_import_media": False,
                    "message": f"Could not verify direct URL: {str(e)}. You can upload the original video.",
                }

    # For YouTube, Twitch, Kick using yt-dlp metadata extraction
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {
                    "url": url,
                    "platform": platform,
                    "title": None,
                    "duration": None,
                    "thumbnail_url": None,
                    "can_import_media": False,
                    "message": f"No media streams found for {platform.capitalize()} URL. You can upload the original video file.",
                }

            is_live = info.get("is_live", False)
            title = info.get("title", f"{platform.capitalize()} Video")
            duration = info.get("duration")
            thumbnail = info.get("thumbnail")

            can_import = not is_live
            message = (
                f"Ready to import {platform.capitalize()} media."
                if can_import
                else "Live streams cannot be imported until ended. Please upload the recorded file instead."
            )

            return {
                "url": url,
                "platform": platform,
                "title": title,
                "duration": duration,
                "thumbnail_url": thumbnail,
                "can_import_media": can_import,
                "message": message,
            }
    except Exception as e:
        logger.warning(f"yt-dlp extract_info failed for {url}: {e}")
        return {
            "url": url,
            "platform": platform,
            "title": f"{platform.capitalize()} Link",
            "duration": None,
            "thumbnail_url": None,
            "can_import_media": False,
            "message": f"Could not extract downloadable media from {platform.capitalize()}: {str(e)}. You can upload the original video file directly.",
        }


def download_remote_media_to_minio(url: str, file_key: str, tmp_dir: str = "/tmp") -> Tuple[str, int]:
    """
    Downloads remote media safely into a local temp file and streams/uploads to MinIO.
    Returns (local_temp_path, file_size).
    """
    validate_url_security(url)
    platform = detect_platform(url)
    os.makedirs(tmp_dir, exist_ok=True)
    out_template = os.path.join(tmp_dir, f"import_%(id)s.%(ext)s")

    if platform == "direct_url":
        # Stream directly using HTTP client
        target_path = os.path.join(tmp_dir, f"direct_import_{os.getpid()}.mp4")
        with httpx.Client(timeout=3600.0, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                validate_url_security(str(response.url))
                response.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
        file_size = os.path.getsize(target_path)
        storage_service.upload_file(target_path, file_key, content_type="video/mp4")
        return target_path, file_size

    # YouTube / Twitch / Kick via yt-dlp
    ydl_opts = {
        "outtmpl": out_template,
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "socket_timeout": 30,
        "retries": 10,
        "fragment_retries": 10,
        "http_chunk_size": 10485760,  # 10MB chunking prevents CDN read timeouts
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_path = ydl.prepare_filename(info)
        # Handle format merged extension
        if not os.path.exists(downloaded_path):
            base_root, _ = os.path.splitext(downloaded_path)
            if os.path.exists(base_root + ".mp4"):
                downloaded_path = base_root + ".mp4"

        if not os.path.exists(downloaded_path):
            raise RuntimeError("Downloaded media file could not be found.")

        file_size = os.path.getsize(downloaded_path)
        import importlib
        import app.services.storage
        importlib.reload(app.services.storage)
        app.services.storage.storage_service.upload_file(downloaded_path, file_key, content_type="video/mp4")
        return downloaded_path, file_size
