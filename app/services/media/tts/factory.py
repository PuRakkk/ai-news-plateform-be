from app.core.config import settings
from app.services.media.tts.base import TTSProvider
from app.services.media.tts.edge_tts_provider import EdgeTTSProvider
from app.services.media.tts.elevenlabs_provider import ElevenLabsTTSProvider
from app.services.media.tts.mock_tts import MockTTSProvider


def get_tts_provider(provider_type: str | None = None) -> TTSProvider:
    """Retrieve configured TTS provider."""
    ptype = provider_type or settings.TTS_PROVIDER
    if ptype == "mock":
        return MockTTSProvider()
    elif ptype == "elevenlabs":
        return ElevenLabsTTSProvider()
    elif ptype == "edge_tts":
        return EdgeTTSProvider()
    return EdgeTTSProvider()

