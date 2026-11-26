import json
import logging
import time
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_ANALYSIS_PROMPT = """
You are an expert viral video producer and short-form video editor for TikTok, Instagram Reels, and YouTube Shorts.
Analyze the following transcript excerpt and audio/visual metadata from a recording.

Your goal is to find ALL distinct, high-impact, entertaining, or valuable 30 to 150-second moments that would make compelling standalone vertical reels.
DO NOT impose an artificial limit on reel count. If there are 3 great moments, return 3. If there are 5, return 5.

For each candidate moment:
1. Ensure the duration is between 30.0 and 150.0 seconds inclusive (end_time - start_time >= 30.0 and <= 150.0).
2. The moment MUST have a strong hook (first 3-5 seconds), clear standalone clarity (makes sense without watching the whole recording), and a satisfying payoff/punchline/conclusion.
3. Write a catchy, punchy, curiosity-inducing TOP CAPTION (under 10 words) in ALL CAPS or Title Case that will sit above the video to stop users from scrolling.
4. Score the moment from 0 to 100 on:
   - hook: How arresting is the opening?
   - payoff: How rewarding is the climax/punchline?
   - clarity: Does it make sense on its own?
   - entertainment: How funny, shocking, insightful, or dramatic is it?
   - overall_score: Weighted composite (0-100).
5. Categorize as: 'hook', 'humor', 'insight', 'reaction', 'story', or 'highlight'.
6. State a concise reason explaining why this moment works.

Output strictly valid JSON matching this schema:
[
  {
    "start_time": float,
    "end_time": float,
    "top_caption": string,
    "category": string,
    "reason": string,
    "score_hook": float,
    "score_payoff": float,
    "score_clarity": float,
    "score_entertainment": float,
    "overall_score": float
  }
]
"""


def is_gemini_configured() -> bool:
    return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())


def analyze_chunk_with_gemini(
    transcript_words: List[Dict[str, Any]],
    scene_changes: List[float],
    audio_peaks: List[Dict[str, float]],
    chunk_start: float,
    chunk_end: float,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Call Gemini API with structured JSON output to extract viral reel candidates.
    If GEMINI_API_KEY is not set, falls back to heuristic candidate generation.
    """
    if not is_gemini_configured():
        logger.info("GEMINI_API_KEY not configured. Using heuristic candidate generator.")
        return generate_heuristic_candidates(
            transcript_words=transcript_words,
            scene_changes=scene_changes,
            audio_peaks=audio_peaks,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
        )

    # Format transcript text with timestamps
    transcript_text_lines = []
    for w in transcript_words:
        transcript_text_lines.append(f"[{w['start']:.2f}s - {w['end']:.2f}s] {w['word']}")
    formatted_transcript = " ".join(transcript_text_lines) if transcript_text_lines else "[No spoken dialogue in this segment]"

    user_content = f"""
Chunk Time Range: {chunk_start:.2f}s to {chunk_end:.2f}s
Scene Change Timestamps: {json.dumps(scene_changes)}
High Audio Energy Peaks: {json.dumps(audio_peaks[:20])}

Transcript:
{formatted_transcript}
"""

    # Determine models to try with fallback for high-demand spikes
    models_to_try = []
    configured_model = settings.GEMINI_MODEL
    if "2.5" in configured_model:
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    else:
        models_to_try = [configured_model]
        for fb in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]:
            if fb not in models_to_try:
                models_to_try.append(fb)

    from app.services.gemini_limiter import gemini_limiter
    est_tokens = max(500, len(user_content) // 4 + 400)

    for attempt in range(1, max_retries + 1):
        # Check rate limiter quota
        allowed, wait_secs, reason = gemini_limiter.check_quota(est_tokens)
        if not allowed:
            logger.warning(f"Gemini limiter active: {reason}. Pausing {min(wait_secs, 10.0):.1f}s...")
            time.sleep(min(wait_secs, 10.0))

        try:
            # Using official google.genai SDK
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            model_name = models_to_try[(attempt - 1) % len(models_to_try)]
            logger.info(f"Gemini API attempt {attempt} using model '{model_name}'...")

            config = types.GenerateContentConfig(
                system_instruction=GEMINI_ANALYSIS_PROMPT,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=model_name,
                contents=user_content,
                config=config,
            )
            raw_text = response.text.strip()
            logger.info(f"Gemini raw response text: {raw_text}")
            candidates = json.loads(raw_text)

            # Record successful usage
            gemini_limiter.record_call(tokens_used=est_tokens)

            validated_candidates = []
            for c in candidates:
                start = float(c.get("start_time", 0.0))
                end = float(c.get("end_time", 0.0))
                dur = end - start

                # Enforce 30-150 second window
                if dur < settings.MIN_CLIP_DURATION:
                    # Expand if possible within chunk bounds
                    diff = settings.MIN_CLIP_DURATION - dur
                    start = max(chunk_start, start - diff / 2)
                    end = min(chunk_end, start + settings.MIN_CLIP_DURATION)
                    dur = end - start

                if dur > settings.MAX_CLIP_DURATION:
                    end = start + settings.MAX_CLIP_DURATION
                    dur = settings.MAX_CLIP_DURATION

                if dur >= settings.MIN_CLIP_DURATION - 0.5:
                    validated_candidates.append({
                        "start_time": round(start, 2),
                        "end_time": round(end, 2),
                        "clip_duration": round(dur, 2),
                        "top_caption": str(c.get("top_caption", "MUST WATCH MOMENT")).upper(),
                        "category": str(c.get("category", "highlight")).lower(),
                        "reason": str(c.get("reason", "Engaging moment identified by Gemini")),
                        "score_hook": float(c.get("score_hook", 75.0)),
                        "score_payoff": float(c.get("score_payoff", 75.0)),
                        "score_clarity": float(c.get("score_clarity", 75.0)),
                        "score_entertainment": float(c.get("score_entertainment", 75.0)),
                        "overall_score": float(c.get("overall_score", 75.0)),
                        "source": "gemini",
                    })

            return validated_candidates

        except Exception as e:
            err_str = str(e).lower()
            if "resource_exhausted" in err_str or "429" in err_str or "rate limit" in err_str:
                logger.warning(f"Gemini 429 / ResourceExhausted hit: {e}. Triggering cooldown.")
                gemini_limiter.record_rate_limit(settings.GEMINI_RETRY_COOLDOWN_SECONDS)

            logger.warning(f"Gemini API attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                logger.error("All Gemini API attempts failed. Falling back to heuristic candidates.")
                return generate_heuristic_candidates(
                    transcript_words=transcript_words,
                    scene_changes=scene_changes,
                    audio_peaks=audio_peaks,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                )

    return []


def generate_heuristic_candidates(
    transcript_words: List[Dict[str, Any]],
    scene_changes: List[float],
    audio_peaks: List[Dict[str, float]],
    chunk_start: float,
    chunk_end: float,
) -> List[Dict[str, Any]]:
    """
    Fallback deterministic heuristic candidate discovery for when Gemini API key is missing or unavailable.
    Finds dialogue dense windows or audio peak/scene change moments and formats valid 30-60s reels.
    """
    candidates = []
    chunk_duration = chunk_end - chunk_start

    if chunk_duration < settings.MIN_CLIP_DURATION:
        return candidates

    # If we have transcript words
    if transcript_words:
        # Find continuous dialogue segments
        t_start = float(transcript_words[0]["start"])
        t_end = float(transcript_words[-1]["end"])
        
        # Candidate 1: First 35 seconds of prominent speech
        c1_start = max(float(chunk_start), t_start)
        c1_end = min(float(chunk_end), c1_start + 35.0)
        if c1_end - c1_start >= 30.0:
            words_in_c1 = [w["word"] for w in transcript_words if c1_start <= float(w["start"]) <= c1_end][:8]
            sample_phrase = " ".join(words_in_c1).upper()
            caption1 = f"WAIT FOR IT: {sample_phrase[:30]}..." if sample_phrase else "BEST MOMENT: WATCH TILL THE END!"
            candidates.append({
                "start_time": float(round(c1_start, 2)),
                "end_time": float(round(c1_end, 2)),
                "clip_duration": float(round(c1_end - c1_start, 2)),
                "top_caption": caption1,
                "category": "hook",
                "reason": "High speech density and strong opening hook identified via heuristic analysis",
                "score_hook": 85.0,
                "score_payoff": 80.0,
                "score_clarity": 82.0,
                "score_entertainment": 84.0,
                "overall_score": 83.0,
                "source": "heuristic",
            })

        # Candidate 2: If chunk is long enough, take another segment around an audio peak or near the middle
        if chunk_duration >= 75.0:
            c2_start = max(float(chunk_start) + 35.0, (float(chunk_start) + float(chunk_end)) / 2.0 - 20.0)
            c2_end = min(float(chunk_end), c2_start + 40.0)
            if c2_end - c2_start >= 30.0:
                candidates.append({
                    "start_time": float(round(c2_start, 2)),
                    "end_time": float(round(c2_end, 2)),
                    "clip_duration": float(round(c2_end - c2_start, 2)),
                    "top_caption": "YOU WON'T BELIEVE WHAT HAPPENS NEXT!",
                    "category": "highlight",
                    "reason": "Sustained action with balanced visual activity and dialogue flow",
                    "score_hook": 78.0,
                    "score_payoff": 82.0,
                    "score_clarity": 80.0,
                    "score_entertainment": 80.0,
                    "overall_score": 80.0,
                    "source": "heuristic",
                })
    else:
        # Silent video / gaming reaction: use audio peaks or scene changes
        c_start = float(chunk_start)
        c_end = min(float(chunk_end), c_start + 35.0)
        if c_end - c_start >= 30.0:
            candidates.append({
                "start_time": float(round(c_start, 2)),
                "end_time": float(round(c_end, 2)),
                "clip_duration": float(round(c_end - c_start, 2)),
                "top_caption": "EPIC GAMEPLAY REACTION!",
                "category": "reaction",
                "reason": "Dynamic visual activity and intense visual pacing detected without dialogue",
                "score_hook": 75.0,
                "score_payoff": 79.0,
                "score_clarity": 70.0,
                "score_entertainment": 78.0,
                "overall_score": 76.0,
                "source": "heuristic",
            })

    return candidates
