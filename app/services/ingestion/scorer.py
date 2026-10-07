from typing import Any
from app.core.log import logger
from app.services.llm.base import LLMProviderAdapter


async def score_article_utility(
    title: str,
    full_text: str,
    llm_provider: LLMProviderAdapter,
    client_criteria: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stage 4: Score article business utility and executive actionability."""
    scores = await llm_provider.score_utility(
        title=title,
        full_text=full_text,
        profile_criteria=client_criteria,
    )
    logger.info(
        f"Utility score for '{title[:40]}...': Composite={scores.get('composite_score')} "
        f"(Act={scores.get('actionability')}, Econ={scores.get('economic_impact')}, Reg={scores.get('regulatory_impact')})"
    )
    return scores
