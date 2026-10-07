import base64
from typing import Any
import httpx

from app.core.config import settings
from app.core.log import logger
from app.services.media.tts.base import TTSCue, TTSProvider, TTSResult
from app.services.media.tts.edge_tts_provider import EdgeTTSProvider


class ElevenLabsTTSProvider(TTSProvider):
    """Neural TTS provider powered by ElevenLabs Text-to-Speech with alignment timestamps."""

    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(
        self,
        api_key: str | None = None,
        default_voice_id: str | None = None,
        model_id: str = "eleven_multilingual_v2",
        fallback_provider: TTSProvider | None = None,
    ) -> None:
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        self.default_voice_id = default_voice_id or "21m00Tcm4TlvDq8ikWAM"  # Default Rachel voice
        self.model_id = model_id
        self.fallback = fallback_provider or EdgeTTSProvider()

    def _build_cues_from_alignment(
        self,
        characters: list[str],
        start_times: list[float],
        end_times: list[float],
    ) -> list[TTSCue]:
        """Aggregate character-level timestamps into kinetic word cues."""
        if not characters or not start_times or not end_times:
            return []

        words: list[str] = []
        word_starts: list[float] = []
        word_ends: list[float] = []

        curr_word_chars: list[str] = []
        curr_start: float | None = None
        curr_end: float = 0.0

        for ch, s, e in zip(characters, start_times, end_times):
            if ch.isspace():
                if curr_word_chars:
                    words.append("".join(curr_word_chars))
                    word_starts.append(curr_start if curr_start is not None else s)
                    word_ends.append(curr_end)
                    curr_word_chars = []
                    curr_start = None
            else:
                if curr_start is None:
                    curr_start = s
                curr_end = e
                curr_word_chars.append(ch)

        if curr_word_chars:
            words.append("".join(curr_word_chars))
            word_starts.append(curr_start if curr_start is not None else 0.0)
            word_ends.append(curr_end)

        # Group words into 3-5 word punchy subtitle cues
        cues: list[TTSCue] = []
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            c_start = word_starts[i]
            c_end = word_ends[min(i + chunk_size - 1, len(word_ends) - 1)]
            cues.append(
                TTSCue(
                    start_sec=round(c_start, 2),
                    end_sec=round(c_end, 2),
                    text=" ".join(chunk_words),
                )
            )

        return cues

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult:
        voice = voice_id or self.default_voice_id
        clean_text = text.strip()
        if not clean_text:
            return TTSResult(audio_bytes=b"", duration_seconds=0.0, voice_id=voice)

        if not self.api_key:
            logger.warning(
                f"ELEVENLABS_API_KEY is not configured. Falling back to {type(self.fallback).__name__} for voice '{voice}'."
            )
            return await self.fallback.synthesize(text, voice_id=None)

        url = f"{self.BASE_URL}/{voice}/with-timestamps"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: dict[str, Any] = {
            "text": clean_text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.error(
                        f"ElevenLabs TTS failed (status {resp.status_code}): {resp.text[:300]}. Falling back."
                    )
                    return await self.fallback.synthesize(text, voice_id=None)

                data = resp.json()
                audio_b64 = data.get("audio_base64", "")
                audio_bytes = base64.b64decode(audio_b64)

                alignment = data.get("alignment", {})
                chars = alignment.get("characters", [])
                starts = alignment.get("character_start_times_seconds", [])
                ends = alignment.get("character_end_times_seconds", [])

                cues = self._build_cues_from_alignment(chars, starts, ends)
                duration = cues[-1].end_sec if cues else (ends[-1] if ends else 0.0)

                logger.info(
                    f"ElevenLabs synthesized {len(audio_bytes)} bytes ({duration:.1f}s, {len(cues)} cues) with voice {voice}"
                )
                return TTSResult(
                    audio_bytes=audio_bytes,
                    duration_seconds=duration,
                    cues=cues,
                    voice_id=voice,
                )
        except Exception as exc:
            logger.warning(f"ElevenLabs request encountered error: {exc}. Falling back to default TTS provider.")
            return await self.fallback.synthesize(text, voice_id=None)
