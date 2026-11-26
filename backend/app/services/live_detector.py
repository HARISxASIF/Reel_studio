import os
import re
import socket
import tempfile
import urllib.parse
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple, List
import httpx
import yt_dlp
from app.services.url_importer import validate_url_security, detect_platform
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


def is_hls_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".m3u8") or ".m3u8?" in url.lower() or "hls" in path


def resolve_relative_url(base_url: str, relative_or_absolute: str) -> str:
    return urllib.parse.urljoin(base_url, relative_or_absolute)


async def probe_direct_hls_stream(url: str) -> Dict[str, Any]:
    """
    Fetch and analyze an HLS playlist with full SSRF protection.
    Determines if live segments are actively streaming.
    """
    validate_url_security(url)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            res = await client.get(url)
            final_url = str(res.url)
            validate_url_security(final_url)

            if res.status_code != 200:
                return {
                    "capability": "waiting_for_stream",
                    "message": f"HLS server responded with status {res.status_code}. Stream may not be active yet.",
                    "resolved_stream_url": final_url,
                    "platform": "direct_hls",
                    "title": "Direct HLS Stream",
                }

            content = res.text
            if not content.startswith("#EXTM3U"):
                return {
                    "capability": "media_unavailable",
                    "message": "URL does not return a valid HLS M3U8 manifest. Please check the URL.",
                    "resolved_stream_url": final_url,
                    "platform": "direct_hls",
                    "title": "Invalid HLS Feed",
                }

            # Check if this is a master playlist containing variant sub-playlists
            if "#EXT-X-STREAM-INF" in content:
                # Find first variant playlist
                lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
                if lines:
                    variant_url = resolve_relative_url(final_url, lines[0])
                    validate_url_security(variant_url)
                    # Recursively probe variant
                    return await probe_direct_hls_stream(variant_url)

            # Media playlist analysis
            is_ended = "#EXT-X-ENDLIST" in content
            segments = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

            if is_ended:
                return {
                    "capability": "stream_ended",
                    "message": "Live broadcast has ended (#EXT-X-ENDLIST detected). You can import the full recording.",
                    "resolved_stream_url": final_url,
                    "platform": "direct_hls",
                    "title": "Completed Stream",
                }

            if not segments:
                return {
                    "capability": "waiting_for_stream",
                    "message": "HLS playlist is present but contains no media segments yet. Waiting for stream to broadcast.",
                    "resolved_stream_url": final_url,
                    "platform": "direct_hls",
                    "title": "Waiting for Stream",
                }

            # Verify first segment URL with SSRF
            sample_segment_url = resolve_relative_url(final_url, segments[0])
            validate_url_security(sample_segment_url)

            return {
                "capability": "live_available",
                "message": f"Live media feed active with {len(segments)} buffer segments available.",
                "resolved_stream_url": final_url,
                "platform": "direct_hls",
                "title": os.path.basename(urllib.parse.urlparse(final_url).path) or "Live HLS Stream",
            }

        except ValueError as ssrf_err:
            raise ssrf_err
        except Exception as e:
            return {
                "capability": "waiting_for_stream",
                "message": f"Could not connect to live feed: {str(e)}. Waiting for stream.",
                "resolved_stream_url": url,
                "platform": "direct_hls",
                "title": "HLS Stream",
            }


async def probe_live_stream_source(url: str) -> Dict[str, Any]:
    """
    Detect platform, validate security, probe capability, and extract media manifest.
    Capabilities:
      - 'live_available': Authorized media stream ready to ingest
      - 'waiting_for_stream': Streamer offline / upcoming
      - 'stream_ended': Broadcast concluded / VOD
      - 'media_unavailable': DRM, player-only, or anti-bot restricted
    """
    validate_url_security(url)
    platform = detect_platform(url)

    # 1. Direct HLS feed check
    if is_hls_url(url) or platform == "direct_url":
        result = await probe_direct_hls_stream(url)
        return result

    # 2. Platform Adapters: YouTube Live, Twitch, Kick
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {
                    "capability": "media_unavailable",
                    "message": f"Could not extract stream metadata from {platform.capitalize()}. You can provide a direct HLS feed.",
                    "resolved_stream_url": None,
                    "platform": platform,
                    "title": f"{platform.capitalize()} Stream",
                    "thumbnail_url": None,
                }

            is_live = info.get("is_live", False)
            live_status = info.get("live_status")
            title = info.get("title", f"{platform.capitalize()} Live Stream")
            thumbnail = info.get("thumbnail")

            # Check status flags
            if live_status == "is_upcoming":
                return {
                    "capability": "waiting_for_stream",
                    "message": f"{platform.capitalize()} broadcast is scheduled or upcoming. Waiting for stream to start.",
                    "resolved_stream_url": None,
                    "platform": platform,
                    "title": title,
                    "thumbnail_url": thumbnail,
                }

            if live_status == "was_live" or (not is_live and info.get("duration")):
                return {
                    "capability": "stream_ended",
                    "message": f"{platform.capitalize()} broadcast has concluded. You can import this recording as a recorded video.",
                    "resolved_stream_url": None,
                    "platform": platform,
                    "title": title,
                    "thumbnail_url": thumbnail,
                }

            # Find direct HLS manifest formats
            formats = info.get("formats", [])
            hls_url = None

            # 1. Prefer master manifest_url (provides master HLS variant with both video and audio tracks)
            for fmt in formats:
                m_url = fmt.get("manifest_url")
                if m_url and (".m3u8" in m_url or "manifest/hls" in m_url):
                    hls_url = m_url
                    break

            # 2. Or prefer a format that has BOTH video and audio streams
            if not hls_url:
                for fmt in reversed(formats):
                    f_url = fmt.get("url", "")
                    protocol = fmt.get("protocol", "")
                    has_v = fmt.get("vcodec") not in (None, "none")
                    has_a = fmt.get("acodec") not in (None, "none")
                    if (protocol in ("m3u8", "m3u8_native") or ".m3u8" in f_url) and has_v and has_a:
                        hls_url = f_url
                        break

            # 3. Fallback to any HLS URL
            if not hls_url:
                for fmt in reversed(formats):
                    f_url = fmt.get("url", "")
                    protocol = fmt.get("protocol", "")
                    if protocol in ("m3u8", "m3u8_native") or ".m3u8" in f_url:
                        hls_url = f_url
                        break

            if not hls_url and info.get("url") and ".m3u8" in info.get("url"):
                hls_url = info.get("url")

            if hls_url:
                try:
                    validate_url_security(hls_url)
                    return {
                        "capability": "live_available",
                        "message": f"Live {platform.capitalize()} stream media feed available.",
                        "resolved_stream_url": hls_url,
                        "platform": platform,
                        "title": title,
                        "thumbnail_url": thumbnail,
                    }
                except ValueError as ssrf_err:
                    return {
                        "capability": "media_unavailable",
                        "message": f"Live manifest resolved to restricted network: {ssrf_err}",
                        "resolved_stream_url": None,
                        "platform": platform,
                        "title": title,
                        "thumbnail_url": thumbnail,
                    }

            if platform == "kick":
                return {
                    "capability": "media_unavailable",
                    "message": "Kick live media stream is protected by Cloudflare verification or embedded player restrictions. Please provide a direct HLS feed or attach the recording later.",
                    "resolved_stream_url": None,
                    "platform": "kick",
                    "title": title,
                    "thumbnail_url": thumbnail,
                }

            if not is_live:
                return {
                    "capability": "waiting_for_stream",
                    "message": f"{platform.capitalize()} channel is currently offline. Waiting for streamer to go live.",
                    "resolved_stream_url": None,
                    "platform": platform,
                    "title": title,
                    "thumbnail_url": thumbnail,
                }

            return {
                "capability": "media_unavailable",
                "message": f"{platform.capitalize()} stream does not expose an authorized direct media stream. Please use a direct HLS feed or upload the recording.",
                "resolved_stream_url": None,
                "platform": platform,
                "title": title,
                "thumbnail_url": thumbnail,
            }

    except Exception as e:
        logger.warning(f"Live probing failed for {url}: {e}")
        err_msg = str(e).lower()
        if "offline" in err_msg or "not currently live" in err_msg:
            return {
                "capability": "waiting_for_stream",
                "message": f"Streamer is currently offline on {platform.capitalize()}.",
                "resolved_stream_url": None,
                "platform": platform,
                "title": f"{platform.capitalize()} Stream",
            }
        return {
            "capability": "media_unavailable",
            "message": f"Could not access live media on {platform.capitalize()}: {str(e)}. You can provide a direct HLS feed or upload the recording.",
            "resolved_stream_url": None,
            "platform": platform,
            "title": f"{platform.capitalize()} Stream",
        }


def extract_live_preview_frame(stream_url: str, output_image_path: str) -> bool:
    """
    Extract a single frame from the live stream with FFmpeg for setup preview.
    Uses fast direct segment extraction for HLS streams to avoid network probing timeouts.
    """
    validate_url_security(stream_url)

    # 1. Fast direct segment extraction for HLS manifests
    if ".m3u8" in stream_url:
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.get(stream_url)
                validate_url_security(str(resp.url))
                if resp.status_code == 200:
                    text = resp.text
                    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
                    if lines:
                        first_line = lines[0]
                        # Check if this is a master playlist pointing to sub-variants
                        if ".m3u8" in first_line or "playlist" in first_line:
                            child_url = resolve_relative_url(str(resp.url), first_line)
                            validate_url_security(child_url)
                            c_resp = client.get(child_url)
                            if c_resp.status_code == 200:
                                c_lines = [l.strip() for l in c_resp.text.splitlines() if l.strip() and not l.startswith("#")]
                                if c_lines:
                                    lines = c_lines
                                    resp = c_resp

                        # Target the latest live edge segment
                        seg_url = resolve_relative_url(str(resp.url), lines[-1])
                        validate_url_security(seg_url)
                        seg_resp = client.get(seg_url)
                        if seg_resp.status_code == 200 and len(seg_resp.content) > 1000:
                            tmp_seg = output_image_path + ".tmp.ts"
                            with open(tmp_seg, "wb") as f:
                                f.write(seg_resp.content)
                            cmd = [
                                "ffmpeg",
                                "-y",
                                "-i", tmp_seg,
                                "-vframes", "1",
                                "-q:v", "2",
                                output_image_path,
                            ]
                            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                            if os.path.exists(tmp_seg):
                                os.remove(tmp_seg)
                            if os.path.exists(output_image_path) and os.path.getsize(output_image_path) > 0:
                                logger.info(f"Successfully extracted live edge preview frame from {seg_url}")
                                return True
        except Exception as e:
            logger.warning(f"Fast segment preview extraction skipped ({e}), falling back to direct ffmpeg...")

    # 2. Fallback to direct FFmpeg probe with timeouts
    cmd = [
        "ffmpeg",
        "-y",
        "-rw_timeout", "10000000",
        "-analyzeduration", "2000000",
        "-probesize", "2000000",
        "-i", stream_url,
        "-vframes", "1",
        "-q:v", "2",
        output_image_path,
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
        return res.returncode == 0 and os.path.exists(output_image_path) and os.path.getsize(output_image_path) > 0
    except Exception as e:
        logger.warning(f"Failed to extract live preview frame from {stream_url}: {e}")
        return False
