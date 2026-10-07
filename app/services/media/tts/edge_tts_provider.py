import edge_tts

from app.core.config import settings
from app.core.log import logger
from app.services.media.tts.base import TTSCue, TTSProvider, TTSResult


class EdgeTTSProvider(TTSProvider):
    """Free neural TTS provider powered by Microsoft Edge Speech engine."""

    def __init__(self, default_voice: str | None = None) -> None:
        self.default_voice = default_voice or settings.TTS_DEFAULT_VOICE or "en-US-ChristopherNeural"

    def _split_into_phrases(
        self, start_sec: float, end_sec: float, text: str, max_words: int = 5
    ) -> list[TTSCue]:
        words = text.split()
        if not words:
            return []
        if len(words) <= max_words:
            return [TTSCue(start_sec=start_sec, end_sec=end_sec, text=text)]

        chunks = [words[i : i + max_words] for i in range(0, len(words), max_words)]
        total_words = len(words)
        duration = max(0.1, end_sec - start_sec)
        result: list[TTSCue] = []
        current_time = start_sec

        for c in chunks:
            chunk_dur = duration * (len(c) / total_words)
            result.append(
                TTSCue(
                    start_sec=round(current_time, 2),
                    end_sec=round(current_time + chunk_dur, 2),
                    text=" ".join(c),
                )
            )
            current_time += chunk_dur

        return result

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult:
        voice = voice_id or self.default_voice
        clean_text = text.strip()
        if not clean_text:
            return TTSResult(audio_bytes=b"", duration_seconds=0.0, voice_id=voice)

        communicate = edge_tts.Communicate(clean_text, voice, boundary="WordBoundary")
        audio_chunks: list[bytes] = []
        raw_word_cues: list[TTSCue] = []
        raw_sentence_cues: list[TTSCue] = []

        try:
            async for chunk in communicate.stream():
                chunk_type = chunk.get("type")
                if chunk_type == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk_type == "WordBoundary":
                    offset_sec = chunk["offset"] / 10_000_000
                    dur_sec = chunk["duration"] / 10_000_000
                    chunk_text = chunk.get("text", "").strip()
                    if chunk_text:
                        raw_word_cues.append(
                            TTSCue(
                                start_sec=round(offset_sec, 3),
                                end_sec=round(offset_sec + dur_sec, 3),
                                text=chunk_text,
                            )
                        )
                elif chunk_type == "SentenceBoundary":
                    offset_sec = chunk["offset"] / 10_000_000
                    dur_sec = chunk["duration"] / 10_000_000
                    chunk_text = chunk.get("text", "").strip()
                    if chunk_text:
                        raw_sentence_cues.append(
                            TTSCue(
                                start_sec=round(offset_sec, 3),
                                end_sec=round(offset_sec + dur_sec, 3),
                                text=chunk_text,
                            )
                        )
        except Exception as exc:
            logger.error(f"EdgeTTS synthesis failed for voice '{voice}': {exc}")
            raise

        audio_bytes = b"".join(audio_chunks)

        # Prefer high-precision word cues; fallback to split sentence cues if word boundaries absent
        if raw_word_cues:
            final_cues = raw_word_cues
        else:
            final_cues = []
            for s_cue in raw_sentence_cues:
                final_cues.extend(
                    self._split_into_phrases(s_cue.start_sec, s_cue.end_sec, s_cue.text, max_words=4)
                )

        duration = final_cues[-1].end_sec if final_cues else 0.0

        # Build SRT string
        srt_lines = []
        for idx, cue in enumerate(final_cues, start=1):
            s_hours = int(cue.start_sec // 3600)
            s_mins = int((cue.start_sec % 3600) // 60)
            s_secs = int(cue.start_sec % 60)
            s_ms = int((cue.start_sec - int(cue.start_sec)) * 1000)

            e_hours = int(cue.end_sec // 3600)
            e_mins = int((cue.end_sec % 3600) // 60)
            e_secs = int(cue.end_sec % 60)
            e_ms = int((cue.end_sec - int(cue.end_sec)) * 1000)

            srt_lines.append(f"{idx}")
            srt_lines.append(
                f"{s_hours:02d}:{s_mins:02d}:{s_secs:02d},{s_ms:03d} --> "
                f"{e_hours:02d}:{e_mins:02d}:{e_secs:02d},{e_ms:03d}"
            )
            srt_lines.append(cue.text)
            srt_lines.append("")

        srt_str = "\n".join(srt_lines)

        logger.info(
            f"EdgeTTS synthesized {len(audio_bytes)} bytes ({duration:.1f}s, {len(final_cues)} cues)"
        )
        return TTSResult(
            audio_bytes=audio_bytes,
            duration_seconds=duration,
            cues=final_cues,
            srt_subtitles=srt_str,
            voice_id=voice,
        )
