import os
import shutil
import time
import subprocess
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import httpx
import json
import logging
from app.config import settings
from app.services.url_importer import validate_url_security
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


@dataclass
class BufferSegment:
    index: int
    url: str
    file_path: str
    duration: float
    timeline_start: float
    timeline_end: float
    size_bytes: int
    referenced_reels: Set[str] = field(default_factory=set)


class LiveBufferManager:
    """
    Manages short media segments, continuous session timeline,
    gap detection, and rolling buffer retention for a single live stream session.
    """

    def __init__(self, session_id: str, buffer_root: Optional[str] = None):
        self.session_id = str(session_id)
        self.buffer_dir = os.path.join(buffer_root or settings.LIVE_BUFFER_DIR, self.session_id)
        os.makedirs(self.buffer_dir, exist_ok=True)
        self.manifest_file = os.path.join(self.buffer_dir, "manifest.json")

        self.segments: List[BufferSegment] = []
        self.coverage_gaps: List[Dict[str, Any]] = []
        self.last_media_sequence: Optional[int] = None
        self.last_timeline_time: float = 0.0
        self.continuous_buffer_seconds: float = 0.0
        self.total_captured_seconds: float = 0.0
        self.seen_urls: Set[str] = set()
        self.min_safe_timeline_mark: float = 0.0

        self._load_manifest()

    def _save_manifest(self):
        try:
            data = {
                "last_media_sequence": self.last_media_sequence,
                "last_timeline_time": self.last_timeline_time,
                "continuous_buffer_seconds": self.continuous_buffer_seconds,
                "total_captured_seconds": self.total_captured_seconds,
                "coverage_gaps": self.coverage_gaps,
                "seen_urls": list(self.seen_urls),
                "segments": [
                    {
                        "index": s.index,
                        "url": s.url,
                        "file_path": s.file_path,
                        "duration": s.duration,
                        "timeline_start": s.timeline_start,
                        "timeline_end": s.timeline_end,
                        "size_bytes": s.size_bytes,
                        "referenced_reels": list(s.referenced_reels),
                    }
                    for s in self.segments
                ],
            }
            tmp = self.manifest_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, self.manifest_file)
        except Exception as e:
            logger.warning(f"Failed to save buffer manifest: {e}")

    def _load_manifest(self):
        if not os.path.exists(self.manifest_file):
            return
        try:
            with open(self.manifest_file, "r") as f:
                data = json.load(f)
            self.last_media_sequence = data.get("last_media_sequence")
            self.last_timeline_time = data.get("last_timeline_time", 0.0)
            self.continuous_buffer_seconds = data.get("continuous_buffer_seconds", 0.0)
            self.total_captured_seconds = data.get("total_captured_seconds", 0.0)
            self.coverage_gaps = data.get("coverage_gaps", [])
            self.seen_urls = set(data.get("seen_urls", []))
            self.segments = [
                BufferSegment(
                    index=s["index"],
                    url=s["url"],
                    file_path=s["file_path"],
                    duration=s["duration"],
                    timeline_start=s["timeline_start"],
                    timeline_end=s["timeline_end"],
                    size_bytes=s["size_bytes"],
                    referenced_reels=set(s.get("referenced_reels", [])),
                )
                for s in data.get("segments", [])
                if os.path.exists(s["file_path"])
            ]
        except Exception as e:
            logger.warning(f"Failed to load buffer manifest: {e}")

    def get_storage_used_bytes(self) -> int:
        total = 0
        try:
            for seg in self.segments:
                if os.path.exists(seg.file_path):
                    total += os.path.getsize(seg.file_path)
        except Exception:
            pass
        return total

    def download_segment_safe(
        self,
        segment_url: str,
        extinf_duration: float,
        media_sequence: Optional[int] = None,
    ) -> Optional[BufferSegment]:
        """
        Download an HLS segment with strict SSRF protection,
        calculate timeline alignment, and track discontinuities.
        """
        if segment_url in self.seen_urls:
            return None

        # SSRF check on segment URL
        try:
            validate_url_security(segment_url)
        except Exception as e:
            logger.error(f"SSRF violation on segment {segment_url}: {e}")
            return None

        seg_idx = len(self.segments)
        ext = os.path.splitext(urllib.parse.urlparse(segment_url).path)[1] or ".ts"
        local_filename = f"seg_{seg_idx:06d}{ext}"
        local_path = os.path.join(self.buffer_dir, local_filename)

        # Download segment with timeout and retry
        download_success = False
        for attempt in range(3):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(segment_url)
                    # Re-verify redirect destination
                    validate_url_security(str(resp.url))
                    if resp.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(resp.content)
                        download_success = True
                        break
                    else:
                        time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.warning(f"Download attempt {attempt+1} failed for {segment_url}: {e}")
                time.sleep(0.5 * (attempt + 1))

        if not download_success or not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
            logger.error(f"Failed to download segment {segment_url} after retries.")
            return None

        size_bytes = os.path.getsize(local_path)

        # Probe actual duration via ffprobe or fallback to extinf_duration
        duration = extinf_duration
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                local_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                probed_dur = float(res.stdout.strip())
                if probed_dur > 0.1:
                    duration = probed_dur
        except Exception:
            pass

        # Gap detection via media sequence discontinuity
        timeline_start = self.last_timeline_time
        if self.last_media_sequence is not None and media_sequence is not None:
            expected_seq = self.last_media_sequence + 1
            if media_sequence > expected_seq:
                gap_seqs = media_sequence - expected_seq
                estimated_gap_dur = gap_seqs * max(duration, 2.0)
                gap_start = timeline_start
                gap_end = timeline_start + estimated_gap_dur
                self.coverage_gaps.append({
                    "start": round(gap_start, 2),
                    "end": round(gap_end, 2),
                    "duration": round(estimated_gap_dur, 2),
                    "reason": f"Discontinuity detected: skipped {gap_seqs} segment(s) (seq {expected_seq} to {media_sequence-1})",
                })
                logger.warning(f"Live buffer gap recorded: {gap_start}s to {gap_end}s ({estimated_gap_dur}s)")
                timeline_start = gap_end
                self.continuous_buffer_seconds = 0.0

        timeline_end = timeline_start + duration

        seg = BufferSegment(
            index=seg_idx,
            url=segment_url,
            file_path=local_path,
            duration=duration,
            timeline_start=timeline_start,
            timeline_end=timeline_end,
            size_bytes=size_bytes,
        )

        self.segments.append(seg)
        self.seen_urls.add(segment_url)
        self.last_media_sequence = media_sequence
        self.last_timeline_time = timeline_end
        self.total_captured_seconds = timeline_end
        self.continuous_buffer_seconds += duration

        # Bounded storage maintenance
        self.purge_expired_segments()
        self._save_manifest()

        return seg

    def purge_expired_segments(self, min_safe_timeline_mark: Optional[float] = None):
        """
        Retain recent footage for analysis windows and manual clips.
        Purge expired segments older than retention threshold if not referenced,
        while protecting any segments still needed by the AI analysis window!
        """
        if min_safe_timeline_mark is not None:
            self.min_safe_timeline_mark = min_safe_timeline_mark
        safe_mark = self.min_safe_timeline_mark

        now_timeline = self.last_timeline_time
        retention_window = settings.LIVE_BUFFER_RETENTION_SECONDS
        max_bytes = settings.LIVE_MAX_STORAGE_MB_PER_SESSION * 1024 * 1024

        total_bytes = self.get_storage_used_bytes()

        for seg in self.segments:
            # Check if segment has expired
            is_expired = (now_timeline - seg.timeline_end) > retention_window
            is_overflow = total_bytes > max_bytes

            # Protect segments still needed by AI analysis unless hard storage cap exceeded
            is_needed_by_ai = (seg.timeline_end >= safe_mark) if safe_mark > 0.0 else False
            if is_needed_by_ai and not is_overflow:
                continue

            if (is_expired or is_overflow) and not seg.referenced_reels:
                if os.path.exists(seg.file_path):
                    try:
                        sz = os.path.getsize(seg.file_path)
                        os.remove(seg.file_path)
                        total_bytes -= sz
                        logger.debug(f"Purged expired live buffer segment {seg.index} ({sz} bytes).")
                    except Exception as e:
                        logger.warning(f"Error purging segment {seg.file_path}: {e}")

    def get_overlapping_segments(self, start_time: float, end_time: float) -> List[BufferSegment]:
        """
        Return segments that overlap the requested [start_time, end_time] range.
        """
        matching = []
        for s in self.segments:
            if s.timeline_end >= start_time and s.timeline_start <= end_time:
                matching.append(s)
        return matching

    def extract_clip_media(
        self,
        start_time: float,
        end_time: float,
        output_path: str,
        reel_id: Optional[str] = None,
    ) -> bool:
        """
        Extract continuous MP4 clip for [start_time, end_time] from buffer segments.
        If reel_id is provided, marks segments as referenced.
        """
        overlapping = self.get_overlapping_segments(start_time, end_time)
        if not overlapping:
            logger.error(f"No buffer segments found for range {start_time:.2f}s - {end_time:.2f}s")
            return False

        # Mark segments as referenced
        if reel_id:
            for s in overlapping:
                s.referenced_reels.add(reel_id)
            self._save_manifest()

        # Check existing segment files
        valid_files = [s.file_path for s in overlapping if os.path.exists(s.file_path)]
        if not valid_files:
            logger.error("Segment files have expired from disk.")
            return False

        # Concat overlapping segments into a single consolidated source clip
        first_seg_start = overlapping[0].timeline_start
        rel_start = max(0.0, start_time - first_seg_start)
        duration = end_time - start_time

        concat_list_file = os.path.join(self.buffer_dir, f"concat_{int(time.time() * 1000)}.txt")
        try:
            with open(concat_list_file, "w") as f:
                for vf in valid_files:
                    safe_path = vf.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_file,
                "-ss", f"{rel_start:.3f}",
                "-t", f"{duration:.3f}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                output_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            success = res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if not success:
                logger.error(f"FFmpeg clip extraction failed: {res.stderr.decode('utf-8', errors='ignore')}")
            return success
        except Exception as e:
            logger.error(f"Error extracting clip media: {e}")
            return False
        finally:
            if os.path.exists(concat_list_file):
                try:
                    os.remove(concat_list_file)
                except Exception:
                    pass

    def cleanup(self):
        """Remove entire local buffer directory for this session."""
        try:
            if os.path.exists(self.buffer_dir):
                shutil.rmtree(self.buffer_dir, ignore_errors=True)
                logger.info(f"Cleaned up live buffer directory for session {self.session_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up live buffer: {e}")
