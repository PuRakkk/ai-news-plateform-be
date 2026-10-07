from app.core.config import settings
from app.services.media.compositor import VideoCompositor
from app.services.media.engine.base import BaseVideoEngine
from app.services.media.engine.did import DIDVideoEngine
from app.services.media.engine.heygen import HeyGenVideoEngine
from app.services.media.engine.mock import MockVideoEngine
from app.services.media.engine.programmatic import ProgrammaticVideoEngine
from app.services.media.storage.base import StorageProvider
from app.services.media.tts.base import TTSProvider


def get_video_engine(
    engine_type: str | None = None,
    storage: StorageProvider | None = None,
    tts: TTSProvider | None = None,
    compositor: VideoCompositor | None = None,
) -> BaseVideoEngine:
    """Factory retrieving the configured or requested VideoEngine adapter."""
    etype = (engine_type or settings.VIDEO_ENGINE or "programmatic").lower().strip()

    if etype == "mock":
        return MockVideoEngine()
    elif etype == "heygen":
        prog = ProgrammaticVideoEngine(storage=storage, tts=tts, compositor=compositor)
        return HeyGenVideoEngine(fallback_engine=prog)
    elif etype == "did":
        prog = ProgrammaticVideoEngine(storage=storage, tts=tts, compositor=compositor)
        return DIDVideoEngine(fallback_engine=prog)
    elif etype == "programmatic":
        return ProgrammaticVideoEngine(storage=storage, tts=tts, compositor=compositor)

    return ProgrammaticVideoEngine(storage=storage, tts=tts, compositor=compositor)
