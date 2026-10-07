from pathlib import Path

from app.services.media.tts.base import TTSCue


def hex_to_ass_color(hex_str: str) -> str:
    """Convert #RRGGBB to ASS &H00BBGGRR& format."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        r, g, b = clean[0:2], clean[2:4], clean[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}&"
    return "&H00FFFFFF&"


def sec_to_ass_time(sec: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cs."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = min(99, int(round((sec - int(sec)) * 100)))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_ass_subtitles(
    cues: list[TTSCue],
    font_family: str = "Arial",
    highlight_hex: str = "#10B981",
    primary_hex: str = "#FFFFFF",
    output_path: Path | str | None = None,
) -> str:
    """Generate high-retention ASS subtitle file with kinetic word-by-word karaoke popping."""
    ass_highlight = hex_to_ass_color(highlight_hex)
    ass_primary = hex_to_ass_color(primary_hex)

    # 1080x1920 mobile viewport, centered in safe lower-third retention zone (MarginV: 390)
    header = f"""[Script Info]
Title: AI News Kinetic Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},56,{ass_primary},&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,4.5,2.5,2,80,80,390,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 1. Normalize all incoming cues into atomic word tokens
    word_cues: list[TTSCue] = []
    for cue in cues:
        raw_words = cue.text.strip().split()
        if not raw_words:
            continue
        if len(raw_words) == 1:
            word_cues.append(cue)
        else:
            total = len(raw_words)
            dur = max(0.1, cue.end_sec - cue.start_sec)
            w_dur = dur / total
            for i, w in enumerate(raw_words):
                w_start = round(cue.start_sec + (i * w_dur), 3)
                w_end = round(cue.start_sec + ((i + 1) * w_dur), 3)
                word_cues.append(TTSCue(start_sec=w_start, end_sec=w_end, text=w))

    # 2. Group into smooth 3-to-4 word phrases with word-by-word active pop styling
    dialogue_lines: list[str] = []
    chunk_size = 4
    for i in range(0, len(word_cues), chunk_size):
        chunk = word_cues[i : i + chunk_size]
        for active_idx, active_word in enumerate(chunk):
            w_start = active_word.start_sec
            w_end = (
                chunk[active_idx + 1].start_sec
                if active_idx + 1 < len(chunk)
                else active_word.end_sec
            )
            w_end = max(w_start + 0.08, w_end)

            phrase_parts: list[str] = []
            for j, w in enumerate(chunk):
                if j == active_idx:
                    phrase_parts.append(
                        f"{{\\c{ass_highlight}\\fscx114\\fscy114}}{w.text}{{\\c{ass_primary}\\fscx100\\fscy100}}"
                    )
                else:
                    phrase_parts.append(w.text)

            styled_text = " ".join(phrase_parts)
            dialogue_lines.append(
                f"Dialogue: 0,{sec_to_ass_time(w_start)},{sec_to_ass_time(w_end)},Default,,0,0,0,,{styled_text}"
            )

    content = header + "\n".join(dialogue_lines) + "\n"

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

    return content
