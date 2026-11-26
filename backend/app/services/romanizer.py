import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Non-Latin unicode pattern covering Arabic/Urdu and Devanagari/Hindi scripts
NON_LATIN_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\u0900-\u097F\uA8E0-\uA8FF]"
)

# Devanagari vowels, matras, and consonants
DEVA_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "अं": "an", "अः": "ah"
}
DEVA_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n", "ः": "h", "्": ""
}
DEVA_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f"
}

# Urdu / Perso-Arabic phonetic mapping
URDU_MAP = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ڈ": "d", "ذ": "z",
    "ر": "r", "ڑ": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q",
    "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "o",
    "ہ": "h", "ھ": "h", "ء": "", "ی": "i", "ے": "e", "ۃ": "h"
}


def contains_non_latin(text: str) -> bool:
    """Return True if text contains Urdu/Arabic or Hindi/Devanagari characters."""
    if not text:
        return False
    return bool(NON_LATIN_PATTERN.search(text))


def transliterate_fallback_word(text: str) -> str:
    """
    Deterministic rule-based phonetic transliteration of Urdu/Hindi into Latin characters.
    Used when Gemini is offline or unavailable.
    """
    if not contains_non_latin(text):
        return text

    res = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        # Devanagari multi-char consonants (with nukta)
        if i + 1 < n and text[i:i+2] in DEVA_CONSONANTS:
            cons = DEVA_CONSONANTS[text[i:i+2]]
            i += 2
            if i < n and text[i] in DEVA_MATRAS:
                res.append(cons + DEVA_MATRAS[text[i]])
                i += 1
            else:
                res.append(cons)
            continue

        if c in DEVA_VOWELS:
            res.append(DEVA_VOWELS[c])
        elif c in DEVA_CONSONANTS:
            cons = DEVA_CONSONANTS[c]
            if i + 1 < n and text[i+1] in DEVA_MATRAS:
                res.append(cons + DEVA_MATRAS[text[i+1]])
                i += 1
            else:
                res.append(cons + "a" if i + 1 < n and text[i+1] in DEVA_CONSONANTS else cons)
        elif c in URDU_MAP:
            res.append(URDU_MAP[c])
        else:
            res.append(c)
        i += 1

    return "".join(res)


def romanize_text(text: str) -> str:
    """Romanize a single text phrase into English Latin script."""
    if not contains_non_latin(text):
        return text
    words = text.split()
    return " ".join(transliterate_fallback_word(w) for w in words)


def romanize_words(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Takes a list of subtitle word objects [{'word': str, 'start': float, 'end': float}].
    If any word is in Urdu or Hindi script, converts it into natural Roman Urdu / Hinglish
    (English/Latin alphabet only) while strictly preserving start and end timestamps.
    """
    if not words:
        return []

    # Check if any word needs romanization
    needs_romanization = any(contains_non_latin(w.get("word", "")) for w in words)
    if not needs_romanization:
        return words

    # If Gemini is configured, use Gemini for natural colloquial Roman Urdu / Hinglish spelling
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            model_name = settings.GEMINI_MODEL
            if "2.5" in model_name:
                model_name = "gemini-3.5-flash-lite"

            # Prepare word payload
            payload_words = [{"word": w["word"], "start": round(w["start"], 2), "end": round(w["end"], 2)} for w in words]
            
            prompt = f"""You are an expert in Urdu, Hindi, Roman Urdu, and Hinglish.
Convert the following transcript words into Roman Urdu and Hinglish (strictly English Latin alphabet only).
Rules:
1. Output MUST use the English/Latin alphabet. No Arabic/Urdu script, no Devanagari script.
2. For Urdu words, use natural, readable Roman Urdu (e.g., 'yeh', 'bohat', 'achha', 'shukriya', 'kya', 'hai').
3. For Hindi words, use natural, readable Hinglish (e.g., 'namaste', 'kaise', 'hota', 'kya', 'baat').
4. Words already in English or Latin alphabet MUST remain unchanged.
5. You MUST return EXACTLY {len(words)} items in the same sequence with identical 'start' and 'end' timestamps.

Input words:
{json.dumps(payload_words, ensure_ascii=False)}

Return strictly valid JSON array of objects with keys: "word", "start", "end".
"""
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw_text = response.text.strip()
            romanized_data = json.loads(raw_text)

            if isinstance(romanized_data, list) and len(romanized_data) == len(words):
                result = []
                for orig, rom in zip(words, romanized_data):
                    clean_word = str(rom.get("word", orig["word"])).strip()
                    # Ensure no lingering non-latin
                    if contains_non_latin(clean_word):
                        clean_word = transliterate_fallback_word(clean_word)
                    result.append({
                        "word": clean_word,
                        "start": orig["start"],
                        "end": orig["end"],
                        "prob": orig.get("prob", 1.0),
                    })
                logger.info(f"Romanized {len(result)} words with Gemini AI into Roman Urdu/Hinglish.")
                return result
            else:
                logger.warning(f"Gemini romanization returned count {len(romanized_data)} vs {len(words)}. Falling back to deterministic mapper.")

        except Exception as e:
            logger.warning(f"Gemini romanization failed: {e}. Falling back to deterministic mapper.")

    # Deterministic fallback: transliterate character-by-character
    result = []
    for w in words:
        clean_word = transliterate_fallback_word(w.get("word", ""))
        result.append({
            "word": clean_word,
            "start": w["start"],
            "end": w["end"],
            "prob": w.get("prob", 1.0),
        })
    logger.info(f"Romanized {len(result)} words via deterministic fallback into Roman Urdu/Hinglish.")
    return result
