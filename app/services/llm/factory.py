from app.core.config import settings
from app.core.log import logger
from app.services.llm.base import LLMProviderAdapter
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider


def get_llm_provider() -> LLMProviderAdapter:
    """Factory to retrieve the active LLM provider adapter based on settings.LLM_PROVIDER."""
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "gemini":
        logger.info(f"Using Gemini LLM Provider (Model: {settings.GEMINI_MODEL})")
        return GeminiProvider()
    elif provider_name == "openai":
        logger.info(f"Using OpenAI LLM Provider (Model: {settings.OPENAI_MODEL})")
        return OpenAIProvider()
    else:
        logger.warning(
            f"Unknown LLM provider '{provider_name}'. Defaulting to OpenAI (Model: {settings.OPENAI_MODEL})"
        )
        return OpenAIProvider()
