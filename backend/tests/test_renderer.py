import os
import tempfile
import pytest
from app.services.renderer import escape_ass_text, format_ass_time, generate_ass_subtitle_file


def test_escape_ass_text():
    raw = "Special \\ characters {and} braces\nnew line"
    escaped = escape_ass_text(raw)
    assert "\\\\" in escaped
    assert "\\{" in escaped
    assert "\\}" in escaped
    assert "\\N" in escaped


def test_format_ass_time():
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(65.5) == "0:01:05.50"
    assert format_ass_time(3661.25) == "1:01:01.25"


def test_generate_ass_subtitle_file():
    words = [
        {"word": "Watch", "start": 0.5, "end": 0.8},
        {"word": "this", "start": 0.9, "end": 1.2},
        {"word": "moment", "start": 1.3, "end": 1.8},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        ass_path = f.name

    try:
        generate_ass_subtitle_file(
            top_caption="EPIC MOMENT HERE",
            subtitles_words=words,
            clip_duration=35.0,
            output_ass_path=ass_path,
        )
        assert os.path.exists(ass_path)
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "[Script Info]" in content
        assert "EPIC MOMENT HERE" in content
        assert "Watch" in content
        assert "Style: TopCaption" in content
        assert "Style: SubtitleNormal,Noto Sans,58," in content

        # Test custom font size
        generate_ass_subtitle_file(
            top_caption="CUSTOM FONT TEST",
            subtitles_words=words,
            clip_duration=35.0,
            output_ass_path=ass_path,
            subtitle_font_size=72,
        )
        with open(ass_path, "r", encoding="utf-8") as f:
            custom_content = f.read()
        assert "Style: SubtitleNormal,Noto Sans,72," in custom_content
        assert "Style: SubtitleActive,Noto Sans,77," in custom_content
    finally:
        if os.path.exists(ass_path):
            os.remove(ass_path)


def test_generate_ass_subtitle_adaptive_wrapping():
    # Long words with large font to verify wrapping
    words = [
        {"word": "SUPERLONGWORDONE", "start": 0.0, "end": 0.5},
        {"word": "SUPERLONGWORDTWO", "start": 0.5, "end": 1.0},
        {"word": "SUPERLONGWORDTHREE", "start": 1.0, "end": 1.5},
        {"word": "SUPERLONGWORDFOUR", "start": 1.5, "end": 2.0},
    ]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        ass_path = f.name
    try:
        generate_ass_subtitle_file(
            top_caption="WRAPPING TEST",
            subtitles_words=words,
            clip_duration=10.0,
            output_ass_path=ass_path,
            subtitle_font_size=66,
        )
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()
        dialogues = [line for line in content.splitlines() if line.startswith("Dialogue: 0")]
        assert len(dialogues) == 4
    finally:
        if os.path.exists(ass_path):
            os.remove(ass_path)


def test_hex_to_ass_color():
    from app.services.renderer import hex_to_ass_color
    assert hex_to_ass_color("#FFE500") == "&H0000E5FF&"  # Yellow: R=FF, G=E5, B=00 -> &H0000E5FF&
    assert hex_to_ass_color("#00FFFF") == "&H00FFFF00&"  # Cyan: R=00, G=FF, B=FF -> &H00FFFF00&
    assert hex_to_ass_color("#22FF44") == "&H0044FF22&"  # Green: R=22, G=FF, B=44 -> &H0044FF22&
    assert hex_to_ass_color("#FF1493") == "&H009314FF&"  # Hot pink
    assert hex_to_ass_color("invalid") == "&H0000E5FF&"   # Default fallback


def test_generate_ass_subtitle_custom_placement_and_style():
    words = [{"word": "Viral", "start": 0.0, "end": 0.5}]
    with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
        ass_path = f.name
    try:
        # Test middle placement (y=0.50 -> MarginV = (1 - 0.5)*1920 = 960) with Montserrat font and Cyan highlight
        generate_ass_subtitle_file(
            top_caption="CENTER TEST",
            subtitles_words=words,
            clip_duration=5.0,
            output_ass_path=ass_path,
            subtitle_font_size=60,
            subtitle_position="middle",
            subtitle_y_percent=0.50,
            subtitle_color="#00FFFF",
            subtitle_font_family="Montserrat",
        )
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check font family is Montserrat
        assert "Style: SubtitleNormal,Montserrat,60," in content
        # Check MarginV is 960
        assert ",960,1" in content
        # Check active word has cyan highlight &H00FFFF00&
        assert "\\c&H00FFFF00&" in content
    finally:
        if os.path.exists(ass_path):
            os.remove(ass_path)

