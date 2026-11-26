import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.services.gemini import is_gemini_configured

logger = logging.getLogger(__name__)

# In-memory LRU / simple cache for hashtag suggestions by reel_id
_HASHTAG_CACHE: Dict[str, Dict[str, Any]] = {}

HASHTAG_PROMPT = """
You are an expert social media strategist and SEO metadata specialist for YouTube Shorts, Instagram Reels, TikTok, and Facebook Reels.
Analyze the following reel's title, description, and transcript snippet.

Generate 10 to 18 highly relevant, high-impact hashtags tailored specifically for gaming and short-form video discovery.
Guidelines:
1. Include specific game, franchise, and character tags (e.g., #GTA6, #ViceCity, #GrandTheftAuto6).
2. Include moment/action/reaction tags based on what happened in the video (e.g., #GTA6EasterEgg, #GamingMoments, #FunnyGaming, #GTAOnline).
3. Include platform discovery tags (e.g., #GamingReels, #Shorts, #GamingCommunity, #ViralGaming).
4. Only include platform/hardware tags like #PS5Pro or #4KGameplay if explicitly relevant or mentioned.
5. Do NOT make false claims about unverified real-time trending stats.
6. All hashtags must begin with '#' and contain only alphanumeric characters.

Output strictly valid JSON:
{
  "hashtags": ["#Tag1", "#Tag2", "#Tag3"],
  "context_keywords": ["keyword1", "keyword2"]
}
"""


def _normalize_tag(tag: str) -> str:
    cleaned = re.sub(r"[^\w]", "", tag)
    if not cleaned:
        return ""
    return f"#{cleaned}"


def _heuristic_hashtags(title: str, description: Optional[str], transcript_text: Optional[str]) -> List[str]:
    combined = f"{title or ''} {description or ''} {transcript_text or ''}".lower()
    tags = set()

    # Domain specific tags based on keywords
    if "gta" in combined or "vice city" in combined or "grand theft auto" in combined:
        tags.update(["#GTA6", "#GTAVI", "#ViceCity", "#GrandTheftAuto", "#GTA6EasterEggs", "#RockstarGames"])
    if "funny" in combined or "laugh" in combined or "lmao" in combined or "😂" in combined or "crazy" in combined:
        tags.update(["#GamingHumor", "#FunnyGaming", "#GamingMemes", "#GamingClips"])
    if "easter egg" in combined or "secret" in combined or "hidden" in combined:
        tags.update(["#EasterEggs", "#GamingSecrets", "#HiddenDetails"])
    if "heist" in combined or "mission" in combined:
        tags.update(["#GamingHeist", "#MissionPassed"])
    if "police" in combined or "cop" in combined or "chase" in combined:
        tags.update(["#PoliceChase", "#WantedLevel"])

    # Extract capitalized or distinct words from title
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    for w in words:
        if len(w) > 3 and w.lower() not in {"this", "that", "with", "from", "your", "what", "video", "clip"}:
            tags.add(f"#{w.capitalize()}")

    # Universal high-performing gaming tags
    tags.update(["#GamingReels", "#Gamer", "#GamingCommunity", "#Gameplay", "#Shorts", "#ViralGaming"])

    # Sort deterministically
    return sorted(list(tags))[:16]


def suggest_hashtags(
    reel_id: str,
    title: str,
    description: Optional[str] = None,
    transcript_text: Optional[str] = None,
    brand_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate contextual hashtags using Gemini with fallback to rule-based generation.
    Results are cached by reel_id.
    """
    cache_key = str(reel_id)
    if cache_key in _HASHTAG_CACHE:
        cached = dict(_HASHTAG_CACHE[cache_key])
        cached["cached"] = True
        return cached

    brand_tags_list = [_normalize_tag(t) for t in (brand_tags or []) if _normalize_tag(t)]
    transcript_snippet = (transcript_text or "")[:1500]

    suggestions = []
    keywords = []

    if is_gemini_configured():
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt_content = f"""
Reel Title / Hook: {title}
Description: {description or 'N/A'}
Transcript Excerpt: {transcript_snippet if transcript_snippet else 'N/A'}
"""
            config = types.GenerateContentConfig(
                system_instruction=HASHTAG_PROMPT,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt_content,
                config=config,
            )
            data = json.loads(response.text.strip())
            raw_tags = data.get("hashtags", [])
            keywords = data.get("context_keywords", [])
            for t in raw_tags:
                norm = _normalize_tag(t)
                if norm and norm not in suggestions:
                    suggestions.append(norm)

        except Exception as e:
            logger.warning(f"Gemini hashtag suggestion failed: {e}. Using heuristic generator.")
            suggestions = _heuristic_hashtags(title, description, transcript_snippet)
    else:
        suggestions = _heuristic_hashtags(title, description, transcript_snippet)

    # Prepend brand tags and deduplicate while preserving order
    final_tags = []
    seen = set()

    for tag in brand_tags_list + suggestions:
        norm = _normalize_tag(tag)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            final_tags.append(norm)

    result = {
        "reel_id": reel_id,
        "suggestions": final_tags,
        "context_keywords": keywords,
        "cached": False,
    }

    _HASHTAG_CACHE[cache_key] = result
    return result
