import uuid
from typing import Any
from sqlmodel import Session

from app.core.log import logger
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.repositories.client_repo import (
    ClientPersonaRepository,
    ClientProfileRepository,
    ClientTopicFilterRepository,
)
from app.repositories.news_repo import ArticleRepository
from app.repositories.script_repo import ScriptBeatRepository, ScriptRepository
from app.services.llm.base import LLMProviderAdapter
from app.services.llm.factory import get_llm_provider

BEAT_TYPES = ["HOOK", "CONTEXT", "CORE_SHIFT", "BUSINESS_IMPACT", "CTA"]
DEFAULT_PERSONA = {
    "persona_role": "AI Chief of Staff",
    "tone_of_voice": "Concise, analytical, authoritative",
    "target_audience": "Business owners, tech executives, and startup founders",
    "default_cta": "Follow for daily executive AI updates.",
}


class ScriptwriterService:
    """Dynamic 5-Beat short-form video scriptwriter tailored to client profiles."""

    def __init__(
        self,
        session: Session,
        llm_provider: LLMProviderAdapter | None = None,
    ) -> None:
        self.session = session
        self.llm_provider = llm_provider or get_llm_provider()
        self.article_repo = ArticleRepository(session)
        self.client_profile_repo = ClientProfileRepository(session)
        self.client_persona_repo = ClientPersonaRepository(session)
        self.client_topic_repo = ClientTopicFilterRepository(session)
        self.script_repo = ScriptRepository(session)
        self.beat_repo = ScriptBeatRepository(session)

    def _resolve_persona_and_filter(
        self, client_id: uuid.UUID | None
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if not client_id:
            return DEFAULT_PERSONA, None

        persona = self.client_persona_repo.get_by_client_id(client_id)
        topic_filter = self.client_topic_repo.get_by_client_id(client_id)

        persona_dict = {
            "persona_role": persona.persona_role if persona else DEFAULT_PERSONA["persona_role"],
            "tone_of_voice": persona.tone_of_voice if persona else DEFAULT_PERSONA["tone_of_voice"],
            "target_audience": persona.target_audience if persona else DEFAULT_PERSONA["target_audience"],
            "default_cta": persona.default_cta if persona else DEFAULT_PERSONA["default_cta"],
        }

        filter_dict = None
        if topic_filter:
            filter_dict = {
                "industries": topic_filter.industries,
                "focus_keywords": topic_filter.focus_keywords,
                "excluded_keywords": topic_filter.excluded_keywords,
            }

        return persona_dict, filter_dict

    def _sanitize_beats(
        self, raw_beats: list[dict[str, Any]], script_title: str
    ) -> list[ScriptBeat]:
        sanitized: list[ScriptBeat] = []

        # If LLM didn't return exactly 5 beats, construct fallbacks for missing ones
        for idx, beat_type in enumerate(BEAT_TYPES, start=1):
            matching_raw = None
            for b in raw_beats:
                if b.get("beat_index") == idx or str(b.get("beat_type", "")).upper() == beat_type:
                    matching_raw = b
                    break

            if matching_raw:
                spoken = str(matching_raw.get("spoken_script", "")).strip()
                vis = str(matching_raw.get("visual_directive", "PRESENTER_CAMERA_A"))
                wb = matching_raw.get("whiteboard_directive")
                sec = int(matching_raw.get("estimated_seconds", 15))
            else:
                spoken = f"Advancement in {script_title} beat {beat_type.lower()}."
                vis = "PRESENTER_CAMERA_A"
                wb = None
                sec = 15

            sanitized.append(
                ScriptBeat(
                    beat_index=idx,
                    beat_type=beat_type,
                    spoken_script=spoken,
                    visual_directive=vis,
                    whiteboard_directive=wb if wb else None,
                    estimated_seconds=max(5, min(sec, 35)),
                )
            )

        return sanitized

    async def generate_script(
        self,
        article_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
    ) -> tuple[Script, list[ScriptBeat]]:
        """Generate a 5-beat grounded script for a winning article and client persona."""
        article = self.article_repo.get_by_id(article_id)
        if not article:
            raise ValueError(f"Article with id {article_id} not found.")

        article_text = article.full_text or article.summary or article.title
        persona_dict, filter_dict = self._resolve_persona_and_filter(client_id)

        logger.info(
            f"Generating script for article='{article.title}' under role='{persona_dict['persona_role']}'"
        )
        llm_result = await self.llm_provider.generate_script(
            article_title=article.title,
            full_text=article_text,
            persona=persona_dict,
            topic_filter=filter_dict,
        )

        title = str(llm_result.get("title", article.title)).strip()
        role = str(llm_result.get("persona_role", persona_dict["persona_role"])).strip()
        cta = str(llm_result.get("call_to_action", persona_dict["default_cta"])).strip()
        raw_beats = llm_result.get("beats", [])

        sanitized_beats = self._sanitize_beats(raw_beats, title)
        total_duration = sum(b.estimated_seconds for b in sanitized_beats)

        # Create or update Script record
        script = self.script_repo.create_script(
            article_id=article_id,
            client_id=client_id,
            title=title,
            persona_role=role,
            total_estimated_duration_sec=total_duration,
            call_to_action=cta,
            status="draft",
        )

        saved_beats = self.beat_repo.replace_beats_for_script(script.id, sanitized_beats)
        logger.info(
            f"Successfully generated script id={script.id} with {len(saved_beats)} beats, duration={total_duration}s"
        )
        return script, saved_beats
