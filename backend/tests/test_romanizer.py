import pytest
from app.services.romanizer import (
    contains_non_latin,
    transliterate_fallback_word,
    romanize_text,
    romanize_words,
)


def test_contains_non_latin():
    # English
    assert not contains_non_latin("Hello world, this is English!")
    assert not contains_non_latin("12345 !@#$%^&*()")

    # Urdu
    assert contains_non_latin("یہ بہت اچھا ہے")
    assert contains_non_latin("کیا حال ہے")

    # Hindi
    assert contains_non_latin("नमस्ते भारत")
    assert contains_non_latin("क्या हाल है")

    # Mixed
    assert contains_non_latin("Hello یہ world")
    assert contains_non_latin("Check out यह video")


def test_transliterate_fallback_urdu():
    urdu_word = "کیا"
    trans = transliterate_fallback_word(urdu_word)
    # Must be English/Latin letters only
    assert not contains_non_latin(trans)
    assert len(trans) > 0


def test_transliterate_fallback_hindi():
    hindi_word = "नमस्ते"
    trans = transliterate_fallback_word(hindi_word)
    # Must be English/Latin letters only
    assert not contains_non_latin(trans)
    assert len(trans) > 0


def test_romanize_words_preserves_timing_and_count():
    words = [
        {"word": "Welcome", "start": 0.0, "end": 0.5, "prob": 0.99},
        {"word": "یہ", "start": 0.5, "end": 1.0, "prob": 0.99},
        {"word": "بہت", "start": 1.0, "end": 1.5, "prob": 0.99},
        {"word": "अच्छा", "start": 1.5, "end": 2.0, "prob": 0.99},
        {"word": "है", "start": 2.0, "end": 2.5, "prob": 0.99},
        {"word": "guys!", "start": 2.5, "end": 3.0, "prob": 0.99},
    ]

    romanized = romanize_words(words)
    assert len(romanized) == len(words)

    for orig, rom in zip(words, romanized):
        # Strict timestamp preservation
        assert rom["start"] == orig["start"]
        assert rom["end"] == orig["end"]
        # Strict English/Latin alphabet only
        assert not contains_non_latin(rom["word"])
        assert len(rom["word"]) > 0

    # First word remains Welcome, last word remains guys!
    assert romanized[0]["word"] == "Welcome"
    assert romanized[-1]["word"] == "guys!"


def test_romanize_text():
    raw = "यह ویڈیو بہت زبردست ہے"
    rom = romanize_text(raw)
    assert not contains_non_latin(rom)
    assert len(rom.split()) == len(raw.split())
