from abc import ABC, abstractmethod
from typing import Any


class LLMProviderAdapter(ABC):
    """Abstract provider adapter for LLM-powered screening, verification, scoring, and scriptwriting."""

    @abstractmethod
    async def screen_candidates(
        self,
        candidates: list[dict[str, Any]],
        top_k: int = 10,
        topic_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Stage 2: Evaluate a batch of raw articles and shortlist top candidates matching client mandate."""
        pass

    @abstractmethod
    async def verify_corroboration(
        self,
        primary_title: str,
        primary_text: str,
        secondary_title: str,
        secondary_text: str,
    ) -> dict[str, Any]:
        """Stage 3: Cross-check factual consistency between independent primary and secondary sources.

        Returns:
            {
                "agreement_score": float,  # 0.00 to 1.00
                "is_verified": bool,       # agreement_score >= 0.75
                "corroboration_notes": str
            }
        """
        pass

    @abstractmethod
    async def score_utility(
        self,
        title: str,
        full_text: str,
        profile_criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Stage 4: Evaluate business utility and executive relevance.

        Returns:
            {
                "composite_score": float,
                "actionability": float,
                "economic_impact": float,
                "regulatory_impact": float,
                "novelty": float,
                "reasoning": str
            }
        """
        pass

    @abstractmethod
    async def generate_script(
        self,
        article_title: str,
        full_text: str,
        persona: dict[str, Any],
        topic_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 2: Generate 5-beat executive short-form video script."""
        pass

    @abstractmethod
    async def audit_claims(
        self,
        beats: list[dict[str, Any]],
        full_text: str,
    ) -> list[dict[str, Any]]:
        """Step 2: Extract atomic factual claims and verify against source text verbatim quotes."""
        pass

    @abstractmethod
    async def revise_script_beat(
        self,
        beat: dict[str, Any],
        ungrounded_claims: list[dict[str, Any]],
        full_text: str,
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        """Step 2: Rewrite an ungrounded beat to strictly ground assertions in article text."""
        pass
