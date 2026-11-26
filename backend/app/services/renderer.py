import os
import subprocess
import logging
from typing import List, Dict, Any, Optional
from app.services.visual_audio import extract_keyframe

from app.services.probe import probe_media_file

logger = logging.getLogger(__name__)


def escape_ass_text(text: str) -> str:
    """Safely escape text for ASS subtitle format."""
    if not text:
        return ""
    # Replace backslashes and curly braces
    cleaned = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    # Replace newlines with ASS \N
    cleaned = cleaned.replace("\r\n", "\\N").replace("\n", "\\N")
    return cleaned


def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS time format: H:MM:SS.cs"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def hex_to_ass_color(hex_str: Optional[str], default: str = "&H0000E5FF&") -> str:
    """
    Convert a hex color string like '#FFE500' or 'FFE500' to ASS format '&H00BBGGRR&'.
    """
    if not hex_str:
        return default
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    if len(s) != 6:
        return default
    try:
        r = s[0:2].upper()
        g = s[2:4].upper()
        b = s[4:6].upper()
        return f"&H00{b}{g}{r}&"
    except Exception:
        return default


def generate_ass_subtitle_file(
    top_caption: str,
    subtitles_words: Optional[List[Dict[str, Any]]],
    clip_duration: float,
    output_ass_path: str,
    subtitle_font_size: int = 58,
    subtitle_position: str = "bottom",
    subtitle_y_percent: float = 0.82,
    subtitle_color: str = "#FFE500",
    subtitle_font_family: str = "Noto Sans",
):
    """
    Generate an ASS (Advanced SubStation Alpha) subtitle file with:
    1. Catchy top caption banner in dedicated top region (Alignment=8).
    2. Dynamic word-by-word highlighted spoken subtitles in customizable position
       (bottom/middle/top or vertical offset), custom highlight color, and custom font family.
    """
    normal_size = max(30, min(100, int(subtitle_font_size or 58)))
    active_size = int(normal_size * 1.08)

    # Calculate vertical margin from bottom based on subtitle_y_percent (0.0 is top, 1.0 is bottom)
    # Alignment 2 is bottom-centered, so MarginV is distance in pixels from bottom edge (PlayResY=1920)
    y_pct = max(0.1, min(0.95, float(subtitle_y_percent if subtitle_y_percent is not None else 0.82)))
    margin_v = max(60, min(1650, int(1920 * (1.0 - y_pct))))

    font_name = (subtitle_font_family or "Noto Sans").strip()
    active_ass_color = hex_to_ass_color(subtitle_color, default="&H0000E5FF&")

    ass_header = f"""[Script Info]
Title: Reel Studio Automated Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopCaption,Noto Sans,54,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,8,40,40,120,1
Style: SubtitleNormal,{font_name},{normal_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,3,2,60,60,{margin_v},1
Style: SubtitleActive,{font_name},{active_size},{active_ass_color},&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,4,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # 1. Top Caption Event (spans entire clip)
    safe_caption = escape_ass_text(top_caption)
    start_str = format_ass_time(0.0)
    end_str = format_ass_time(clip_duration)
    events.append(f"Dialogue: 1,{start_str},{end_str},TopCaption,,0,0,0,,{{\\b1\\an8}}{safe_caption}")

    # 2. Spoken Subtitles with Word-Level Karaoke Highlight
    if subtitles_words:
        # Dynamic wrapping based on font size to prevent line truncation
        phrase_size = 3 if normal_size >= 64 else (4 if normal_size >= 50 else 5)
        max_chars = 22 if normal_size >= 64 else (30 if normal_size >= 50 else 38)

        phrases = []
        current_phrase = []
        current_len = 0
        for w in subtitles_words:
            word_str = w.get("word", "")
            if current_phrase and (len(current_phrase) >= phrase_size or current_len + len(word_str) > max_chars):
                phrases.append(current_phrase)
                current_phrase = [w]
                current_len = len(word_str)
            else:
                current_phrase.append(w)
                current_len += len(word_str) + 1
        if current_phrase:
            phrases.append(current_phrase)

        for chunk in phrases:
            # For each word in the phrase, render the phrase during that word's duration with that word highlighted
            for word_idx, active_word in enumerate(chunk):
                w_start = format_ass_time(active_word["start"])
                w_end = format_ass_time(active_word["end"])

                # Build line text: active word highlighted with user-configured color
                line_parts = []
                for idx, w in enumerate(chunk):
                    word_clean = escape_ass_text(w["word"])
                    if idx == word_idx:
                        line_parts.append(f"{{\\c{active_ass_color}\\b1}}{word_clean}{{\\r}}")
                    else:
                        line_parts.append(f"{{\\c&H00FFFFFF&\\b1}}{word_clean}{{\\r}}")

                formatted_line = " ".join(line_parts)
                events.append(f"Dialogue: 0,{w_start},{w_end},SubtitleNormal,,0,0,0,,{formatted_line}")

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(events) + "\n")


def render_reel_video(
    source_media_path: str,
    output_mp4_path: str,
    source_start: float,
    clip_duration: float,
    framing_mode: str,
    pan_x_offset: float,
    top_caption: str,
    subtitles_words: Optional[List[Dict[str, Any]]],
    subtitle_font_size: int = 58,
    has_audio: bool = True,
    split_facecam_crop: Optional[Dict[str, Any]] = None,
    split_gameplay_crop: Optional[Dict[str, Any]] = None,
    split_order: str = "facecam_top",
    split_ratio: float = 0.35,
    subtitle_position: str = "bottom",
    subtitle_y_percent: float = 0.82,
    subtitle_color: str = "#FFE500",
    subtitle_font_family: str = "Noto Sans",
) -> str:
    """
    Renders 1080x1920 vertical MP4 reel with H.264 video, AAC audio,
    burned top caption, and word-by-word subtitles.
    Supports framing modes: 'crop', 'fit', 'pan', and 'split' (Gaming Split Screen).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)
    ass_path = output_mp4_path + ".ass"

    # Generate ASS file
    generate_ass_subtitle_file(
        top_caption=top_caption,
        subtitles_words=subtitles_words,
        clip_duration=clip_duration,
        output_ass_path=ass_path,
        subtitle_font_size=subtitle_font_size,
        subtitle_position=subtitle_position,
        subtitle_y_percent=subtitle_y_percent,
        subtitle_color=subtitle_color,
        subtitle_font_family=subtitle_font_family,
    )

    # Escape path for FFmpeg subtitles filter
    # On linux/posix, path in subtitles='path' needs escaping of : and \
    escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")

    # Build video filter complex depending on framing mode
    if framing_mode == "fit":
        # Fit mode: blurred 1080x1920 background + sharp aspect-ratio preserved foreground in center
        filter_complex = (
            f"[0:v]split=2[bg_in][fg_in];"
            f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
            f"[fg_in]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]subtitles='{escaped_ass_path}'[v]"
        )
    elif framing_mode == "pan":
        # Pan mode: custom horizontal offset (-1.0 left to 1.0 right)
        filter_complex = (
            f"[0:v]crop=ih*9/16:ih:'(iw-ow)*(0.5+{pan_x_offset}*0.5)':0,scale=1080:1920[base];"
            f"[base]subtitles='{escaped_ass_path}'[v]"
        )
    elif framing_mode == "split":
        # Gaming Split Screen mode:
        # Dual crop regions (facecam + gameplay) composited into vertical 1080x1920
        try:
            probe_info = probe_media_file(source_media_path)
            src_w = probe_info.get("width", 1920)
            src_h = probe_info.get("height", 1080)
        except Exception:
            src_w, src_h = 1920, 1080

        fc_crop = split_facecam_crop or {"x": 0.70, "y": 0.05, "width": 0.28, "height": 0.35}
        gp_crop = split_gameplay_crop or {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}

        ratio = max(0.15, min(0.85, float(split_ratio or 0.35)))
        h_top = int(round(1920 * ratio)) // 2 * 2
        h_bot = 1920 - h_top

        is_fc_top = (split_order or "facecam_top") == "facecam_top"
        top_box = fc_crop if is_fc_top else gp_crop
        bot_box = gp_crop if is_fc_top else fc_crop

        def get_effective_crop_pixels(box: Dict[str, Any], pane_w: int, pane_h: int, total_w: int, total_h: int):
            bx = max(0.0, min(1.0, float(box.get("x", 0.0))))
            by = max(0.0, min(1.0, float(box.get("y", 0.0))))
            bw = max(0.01, min(1.0 - bx, float(box.get("width", 1.0))))
            bh = max(0.01, min(1.0 - by, float(box.get("height", 1.0))))

            src_ar = total_w / total_h
            crop_ar = (bw / bh) * src_ar
            pane_ar = pane_w / pane_h

            eff_w = bw
            eff_h = bh
            eff_x = bx
            eff_y = by

            if crop_ar > pane_ar:
                # Crop is wider than pane -> center crop horizontally within the selected region
                eff_w = (bh * pane_ar) / src_ar
                eff_x = bx + (bw - eff_w) / 2.0
            elif crop_ar < pane_ar:
                # Crop is taller than pane -> center crop vertically within the selected region
                eff_h = (bw * src_ar) / pane_ar
                eff_y = by + (bh - eff_h) / 2.0

            px = int(round(eff_x * total_w)) // 2 * 2
            py = int(round(eff_y * total_h)) // 2 * 2
            pw = max(16, int(round(eff_w * total_w))) // 2 * 2
            ph = max(16, int(round(eff_h * total_h))) // 2 * 2

            # Clamp so crop boundaries strictly stay within source video
            px = max(0, min(total_w - 16, px))
            py = max(0, min(total_h - 16, py))
            pw = min(pw, total_w - px) // 2 * 2
            ph = min(ph, total_h - py) // 2 * 2

            return px, py, pw, ph

        x1, y1, w1, h1 = get_effective_crop_pixels(top_box, 1080, h_top, src_w, src_h)
        x2, y2, w2, h2 = get_effective_crop_pixels(bot_box, 1080, h_bot, src_w, src_h)

        filter_complex = (
            f"[0:v]split=2[src1][src2];"
            f"[src1]crop={w1}:{h1}:{x1}:{y1},"
            f"scale=1080:{h_top}:force_original_aspect_ratio=increase,"
            f"crop=1080:{h_top}[top_pane];"
            f"[src2]crop={w2}:{h2}:{x2}:{y2},"
            f"scale=1080:{h_bot}:force_original_aspect_ratio=increase,"
            f"crop=1080:{h_bot}[bot_pane];"
            f"[top_pane][bot_pane]vstack=inputs=2[base];"
            f"[base]subtitles='{escaped_ass_path}'[v]"
        )
    else:
        # Default 'crop': center crop to 9:16
        filter_complex = (
            f"[0:v]crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920[base];"
            f"[base]subtitles='{escaped_ass_path}'[v]"
        )

    input_args = [
        "-ss", str(source_start),
        "-i", source_media_path,
    ]
    if not has_audio:
        input_args.extend([
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ])

    cmd = [
        "ffmpeg",
        "-y",
        *input_args,
        "-t", str(clip_duration),
        "-filter_complex", filter_complex,
        "-map", "[v]",
    ]

    if has_audio:
        cmd.extend([
            "-map", "0:a?",
            "-c:a", "aac",
            "-b:a", "192k",
        ])
    else:
        cmd.extend([
            "-map", "1:a",
            "-c:a", "aac",
            "-shortest",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_mp4_path,
    ])

    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
        logger.info(f"Rendered reel successfully: {output_mp4_path}")
        return output_mp4_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg rendering failed: {e.stderr}")
        raise RuntimeError(f"Rendering failed: {e.stderr[-500:]}")
    finally:
        # Keep or cleanup ASS file
        if os.path.exists(ass_path):
            os.remove(ass_path)
