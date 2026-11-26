import os
import logging
from typing import List, Dict, Any, Optional
from faster_whisper import WhisperModel
from app.config import settings

logger = logging.getLogger(__name__)

# Singleton WhisperModel instance
_whisper_model: Optional[WhisperModel] = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        logger.info(
            f"Loading faster-whisper model '{settings.WHISPER_MODEL}' on {settings.WHISPER_DEVICE} ({settings.WHISPER_COMPUTE_TYPE})..."
        )
        os.makedirs(settings.WHISPER_CACHE_DIR, exist_ok=True)
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            download_root=settings.WHISPER_CACHE_DIR,
        )
        logger.info("faster-whisper model loaded successfully.")
    return _whisper_model


def transcribe_media_segment(
    media_path: str,
    start_time: float,
    duration: float,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Transcribe a segment of a media file starting at `start_time` with length `duration`.
    Returns word-level timestamps relative to the SOURCE timeline (i.e. start_time + word.start).
    """
    model = get_whisper_model()
    
    # We can pass an extracted audio segment or pass the media file directly with start/duration if supported,
    # or extract a fast WAV segment using ffmpeg to guarantee exact chunk extraction without loading the whole file into RAM!
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        tmp_audio_path = tmp_audio.name

    try:
        # Extract audio chunk quickly using FFmpeg stream copy / fast PCM WAV (16kHz mono recommended for Whisper)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", media_path,
            "-t", str(duration),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            tmp_audio_path,
        ]
        ffmpeg_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if ffmpeg_res.returncode != 0:
            logger.warning(
                f"Audio extraction from {media_path} at {start_time}s returned {ffmpeg_res.returncode}: "
                f"{ffmpeg_res.stderr.decode('utf-8', errors='ignore')[:200]}. Skipping transcription."
            )
            return []

        if not os.path.exists(tmp_audio_path) or os.path.getsize(tmp_audio_path) == 0:
            return []

        segments, info = model.transcribe(
            tmp_audio_path,
            beam_size=5,
            word_timestamps=True,
            language=language,  # None will auto-detect Urdu, Hindi, English, etc.
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        words_list: List[Dict[str, Any]] = []
        for segment in segments:
            if segment.words:
                for word_obj in segment.words:
                    clean_word = word_obj.word.strip()
                    if clean_word:
                        words_list.append({
                            "word": clean_word,
                            # Convert offset from chunk-relative to source-relative
                            "start": round(start_time + word_obj.start, 3),
                            "end": round(start_time + word_obj.end, 3),
                            "prob": round(word_obj.probability, 3),
                        })

        from app.services.romanizer import romanize_words
        return romanize_words(words_list)

    except Exception as e:
        logger.error(f"Transcription failed for chunk at {start_time}s: {e}")
        return []
    finally:
        if os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)


def reconcile_transcript_words(
    existing_words: List[Dict[str, Any]],
    new_words: List[Dict[str, Any]],
    overlap_start: float,
    overlap_end: float,
) -> List[Dict[str, Any]]:
    """
    Reconciles duplicate transcript words introduced by chunk overlap.
    Any words in new_words that occur before the midpoint of the overlap or duplicate
    existing words are deduplicated based on timestamp proximity and word similarity.
    """
    if not existing_words:
        return new_words

    if not new_words:
        return existing_words

    midpoint = (overlap_start + overlap_end) / 2.0

    # Words strictly before midpoint from existing_words
    prior_words = [w for w in existing_words if w["start"] < midpoint]

    # Words strictly after midpoint from new_words
    subsequent_words = [w for w in new_words if w["start"] >= midpoint]

    # Combine and sort by start timestamp
    combined = sorted(prior_words + subsequent_words, key=lambda w: w["start"])
    return combined
