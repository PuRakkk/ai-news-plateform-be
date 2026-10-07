import subprocess

from app.core.log import logger
from app.services.media.tts.base import TTSCue, TTSProvider, TTSResult


class MockTTSProvider(TTSProvider):
    """Deterministic mock TTS provider for unit testing and offline development."""

    def __init__(self, words_per_second: float = 2.5) -> None:
        self.words_per_second = words_per_second

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult:
        words = text.split()
        total_words = len(words)
        duration = max(2.0, round(total_words / self.words_per_second, 2)) if total_words > 0 else 2.0

        # Generate timed phrases
        cues: list[TTSCue] = []
        if total_words > 0:
            chunk_size = 5
            chunks = [words[i : i + chunk_size] for i in range(0, total_words, chunk_size)]
            time_per_chunk = duration / len(chunks)
            current_time = 0.0
            for chunk in chunks:
                end_time = round(current_time + time_per_chunk, 2)
                cues.append(
                    TTSCue(
                        start_sec=round(current_time, 2),
                        end_sec=end_time,
                        text=" ".join(chunk),
                    )
                )
                current_time = end_time

        # Generate silent or sine audio using FFmpeg
        audio_bytes = b""
        try:
            cmd = [
                "ffmpeg",
                "-f", "lavfi",
                "-i", f"sine=frequency=440:duration={duration}",
                "-c:a", "libmp3lame",
                "-b:a", "64k",
                "-f", "mp3",
                "pipe:1",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            audio_bytes = proc.stdout
        except Exception as exc:
            logger.warning(f"FFmpeg mock audio generation failed ({exc}), using fallback dummy bytes")
            audio_bytes = b"\xff\xfb\x90\x64" * 100  # Minimal mock MP3 frames

        # Build SRT
        srt_lines = []
        for idx, cue in enumerate(cues, start=1):
            s_secs = int(cue.start_sec)
            s_ms = int((cue.start_sec - s_secs) * 1000)
            e_secs = int(cue.end_sec)
            e_ms = int((cue.end_sec - e_secs) * 1000)
            srt_lines.append(f"{idx}")
            srt_lines.append(f"00:00:{s_secs:02d},{s_ms:03d} --> 00:00:{e_secs:02d},{e_ms:03d}")
            srt_lines.append(cue.text)
            srt_lines.append("")

        return TTSResult(
            audio_bytes=audio_bytes,
            duration_seconds=duration,
            cues=cues,
            srt_subtitles="\n".join(srt_lines),
            voice_id=voice_id or "mock-voice",
        )
