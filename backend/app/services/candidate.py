import logging
from typing import List, Dict, Any, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


def calculate_overlap_ratio(start1: float, end1: float, start2: float, end2: float) -> float:
    """Calculate Intersection over Union (IoU) of two time intervals."""
    inter_start = max(start1, start2)
    inter_end = min(end1, end2)
    intersection = max(0.0, inter_end - inter_start)

    len1 = end1 - start1
    len2 = end2 - start2
    union = len1 + len2 - intersection

    return (intersection / union) if union > 0 else 0.0


def deduplicate_candidates(candidates: List[Dict[str, Any]], iou_threshold: float = 0.5) -> List[Dict[str, Any]]:
    """
    Deduplicate alternate cuts of the same event or near-identical moments.
    Keeps the higher scoring candidate when IoU exceeds iou_threshold.
    """
    if not candidates:
        return []

    # Sort descending by overall_score
    sorted_candidates = sorted(candidates, key=lambda c: c.get("overall_score", 0), reverse=True)
    kept = []

    for cand in sorted_candidates:
        c_start = cand["start_time"]
        c_end = cand["end_time"]
        is_duplicate = False

        for existing in kept:
            e_start = existing["start_time"]
            e_end = existing["end_time"]
            if calculate_overlap_ratio(c_start, c_end, e_start, e_end) >= iou_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(cand)

    # Re-sort chronologically by start_time
    return sorted(kept, key=lambda c: c["start_time"])


def build_clip_subtitles(
    all_words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
) -> List[Dict[str, Any]]:
    """
    Extract words falling inside [clip_start, clip_end] and convert timestamps
    from source-relative to clip-relative time.
    """
    clip_words: List[Dict[str, Any]] = []

    for w in all_words:
        w_start = w["start"]
        w_end = w["end"]

        # Word must overlap the clip window
        if w_end > clip_start and w_start < clip_end:
            # Clamp to clip boundaries and make relative to clip start
            rel_start = max(0.0, w_start - clip_start)
            rel_end = min(clip_end - clip_start, w_end - clip_start)

            if rel_end > rel_start:
                clip_words.append({
                    "word": w["word"],
                    "start": round(rel_start, 3),
                    "end": round(rel_end, 3),
                    "prob": w.get("prob", 1.0),
                })

    return clip_words
