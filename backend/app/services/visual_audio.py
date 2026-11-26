import os
import re
import subprocess
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def detect_scene_changes(media_path: str, start_time: float, duration: float, threshold: float = 0.35) -> List[float]:
    """
    Detect visual scene changes in a media segment using FFmpeg scene filter.
    Returns timestamps relative to the source timeline.
    """
    cmd = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", media_path,
        "-t", str(duration),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null",
        "-",
    ]
    scene_timestamps: List[float] = []
    try:
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, check=False)
        # Parse showinfo output: pts_time:12.345
        for line in proc.stderr.splitlines():
            if "showinfo" in line and "pts_time:" in line:
                m = re.search(r"pts_time:([0-9.]+)", line)
                if m:
                    rel_time = float(m.group(1))
                    scene_timestamps.append(round(start_time + rel_time, 2))
    except Exception as e:
        logger.warning(f"Scene detection failed at {start_time}s: {e}")

    return scene_timestamps


def detect_audio_peaks(media_path: str, start_time: float, duration: float) -> List[Dict[str, float]]:
    """
    Detect high audio energy / volume peaks in a media segment.
    Returns list of {"time": timestamp, "level": peak_db}.
    """
    cmd = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", media_path,
        "-t", str(duration),
        "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level:file=-",
        "-f", "null",
        "-",
    ]
    peaks: List[Dict[str, float]] = []
    try:
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, check=False)
        current_time = 0.0
        for line in proc.stderr.splitlines():
            if "pts_time:" in line:
                m = re.search(r"pts_time:([0-9.]+)", line)
                if m:
                    current_time = float(m.group(1))
            elif "lavfi.astats.Overall.Peak_level=" in line:
                val_str = line.split("=")[-1].strip()
                try:
                    level = float(val_str)
                    # -12dB or louder is typically exciting / speech peak
                    if level > -15.0:
                        peaks.append({
                            "time": round(start_time + current_time, 2),
                            "level": round(level, 2),
                        })
                except ValueError:
                    pass
    except Exception as e:
        logger.warning(f"Audio peak detection failed at {start_time}s: {e}")

    return peaks


def extract_keyframe(media_path: str, timestamp: float, output_path: str, width: int = 480):
    """
    Extract a single frame image at `timestamp` for visual evaluation or thumbnail.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", media_path,
        "-vframes", "1",
        "-vf", f"scale={width}:-1",
        "-q:v", "3",
        output_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
