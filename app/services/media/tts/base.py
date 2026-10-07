import abc
from dataclasses import dataclass, field


@dataclass
class TTSCue:
    """Timed subtitle cue."""
    start_sec: float
    end_sec: float
    text: str


@dataclass
class TTSResult:
    """Result of speech synthesis."""
    audio_bytes: bytes
    duration_seconds: float
    cues: list[TTSCue] = field(default_factory=list)
    srt_subtitles: str = ""
    voice_id: str = ""


class TTSProvider(abc.ABC):
    """Abstract interface for text-to-speech synthesis."""

    @abc.abstractmethod
    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult:
        """Synthesize spoken audio from script text with subtitle alignment."""
        pass
