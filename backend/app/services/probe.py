import json
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def probe_media_file(file_path: str) -> Dict[str, Any]:
    """
    Run ffprobe on the given media file and extract container, stream, and track info.
    Raises RuntimeError if ffprobe fails or media is corrupt.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe execution failed: {e.stderr}")
        raise RuntimeError(f"FFprobe failed to inspect media: {e.stderr}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse FFprobe JSON output: {e}")

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise RuntimeError("The file does not contain a valid video stream.")

    # Duration parsing
    duration_str = format_info.get("duration") or video_stream.get("duration")
    duration = float(duration_str) if duration_str else 0.0

    # FPS parsing
    fps = 30.0
    r_frame_rate = video_stream.get("r_frame_rate", "30/1")
    if "/" in r_frame_rate:
        num, den = r_frame_rate.split("/")
        if float(den) > 0:
            fps = float(num) / float(den)

    raw_width = int(video_stream.get("width", 0))
    raw_height = int(video_stream.get("height", 0))

    # Detect video rotation (e.g. smartphone recordings with 90 or 270 degree metadata)
    rotate = 0
    tags = video_stream.get("tags") or {}
    if "rotate" in tags:
        try:
            rotate = int(tags["rotate"])
        except (ValueError, TypeError):
            rotate = 0
    for side in video_stream.get("side_data_list", []):
        if "rotation" in side:
            try:
                rotate = int(side["rotation"])
            except (ValueError, TypeError):
                pass

    if abs(rotate) in (90, 270):
        display_width, display_height = raw_height, raw_width
    else:
        display_width, display_height = raw_width, raw_height

    video_codec = video_stream.get("codec_name", "unknown")
    audio_codec = audio_stream.get("codec_name", None) if audio_stream else None
    audio_channels = int(audio_stream.get("channels", 0)) if audio_stream else 0
    bitrate = int(format_info.get("bit_rate", 0))

    return {
        "duration": duration,
        "width": display_width,
        "height": display_height,
        "raw_width": raw_width,
        "raw_height": raw_height,
        "rotation": rotate,
        "fps": round(fps, 2),
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "has_audio": audio_stream is not None,
        "audio_channels": audio_channels,
        "bitrate": bitrate,
        "streams_count": len(streams),
    }
