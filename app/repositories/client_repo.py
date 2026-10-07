import json
import uuid
from typing import Sequence
from sqlmodel import Session, select

from app.models.client import (
    ClientBrandKit,
    ClientPersona,
    ClientProfile,
    ClientTopicFilter,
)
from app.repositories.base import BaseRepository


class ClientProfileRepository(BaseRepository[ClientProfile]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClientProfile, session)

    def get_by_slug(self, slug: str) -> ClientProfile | None:
        statement = select(ClientProfile).where(ClientProfile.slug == slug)
        return self.session.exec(statement).first()

    def get_active_clients(self) -> Sequence[ClientProfile]:
        statement = select(ClientProfile).where(ClientProfile.is_active == True)  # noqa: E712
        return self.session.exec(statement).all()

    def create_client(self, name: str, slug: str, is_active: bool = True) -> ClientProfile:
        client = ClientProfile(name=name, slug=slug, is_active=is_active)
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)
        return client

    def get_client_bundle(
        self, client_id: uuid.UUID
    ) -> tuple[ClientProfile | None, ClientPersona | None, ClientTopicFilter | None]:
        client = self.session.get(ClientProfile, client_id)
        if not client:
            return None, None, None

        persona_stmt = select(ClientPersona).where(ClientPersona.client_id == client_id)
        persona = self.session.exec(persona_stmt).first()

        filter_stmt = select(ClientTopicFilter).where(ClientTopicFilter.client_id == client_id)
        topic_filter = self.session.exec(filter_stmt).first()

        return client, persona, topic_filter


class ClientPersonaRepository(BaseRepository[ClientPersona]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClientPersona, session)

    def get_by_client_id(self, client_id: uuid.UUID) -> ClientPersona | None:
        statement = select(ClientPersona).where(ClientPersona.client_id == client_id)
        return self.session.exec(statement).first()

    def upsert_persona(
        self,
        client_id: uuid.UUID,
        persona_role: str = "AI Chief of Staff",
        tone_of_voice: str = "Concise, analytical, authoritative",
        target_audience: str = "Business owners, tech executives, and startup founders",
        default_cta: str = "Follow for daily executive AI updates.",
    ) -> ClientPersona:
        existing = self.get_by_client_id(client_id)
        if existing:
            existing.persona_role = persona_role
            existing.tone_of_voice = tone_of_voice
            existing.target_audience = target_audience
            existing.default_cta = default_cta
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        persona = ClientPersona(
            client_id=client_id,
            persona_role=persona_role,
            tone_of_voice=tone_of_voice,
            target_audience=target_audience,
            default_cta=default_cta,
        )
        self.session.add(persona)
        self.session.commit()
        self.session.refresh(persona)
        return persona


class ClientTopicFilterRepository(BaseRepository[ClientTopicFilter]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClientTopicFilter, session)

    def get_by_client_id(self, client_id: uuid.UUID) -> ClientTopicFilter | None:
        statement = select(ClientTopicFilter).where(ClientTopicFilter.client_id == client_id)
        return self.session.exec(statement).first()

    def upsert_topic_filter(
        self,
        client_id: uuid.UUID,
        industries: list[str] | str = "[]",
        focus_keywords: list[str] | str = "[]",
        excluded_keywords: list[str] | str = "[]",
        weight_actionability: float = 0.40,
        weight_economic: float = 0.30,
        weight_regulatory: float = 0.20,
        weight_novelty: float = 0.10,
    ) -> ClientTopicFilter:
        ind_str = json.dumps(industries) if isinstance(industries, list) else industries
        foc_str = json.dumps(focus_keywords) if isinstance(focus_keywords, list) else focus_keywords
        exc_str = json.dumps(excluded_keywords) if isinstance(excluded_keywords, list) else excluded_keywords

        existing = self.get_by_client_id(client_id)
        if existing:
            existing.industries = ind_str
            existing.focus_keywords = foc_str
            existing.excluded_keywords = exc_str
            existing.weight_actionability = weight_actionability
            existing.weight_economic = weight_economic
            existing.weight_regulatory = weight_regulatory
            existing.weight_novelty = weight_novelty
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        topic_filter = ClientTopicFilter(
            client_id=client_id,
            industries=ind_str,
            focus_keywords=foc_str,
            excluded_keywords=exc_str,
            weight_actionability=weight_actionability,
            weight_economic=weight_economic,
            weight_regulatory=weight_regulatory,
            weight_novelty=weight_novelty,
        )
        self.session.add(topic_filter)
        self.session.commit()
        self.session.refresh(topic_filter)
        return topic_filter



class ClientBrandKitRepository(BaseRepository[ClientBrandKit]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClientBrandKit, session)

    def get_by_client_id(self, client_id: uuid.UUID) -> ClientBrandKit | None:
        statement = select(ClientBrandKit).where(ClientBrandKit.client_id == client_id)
        return self.session.exec(statement).first()

    def upsert_brand_kit(
        self,
        client_id: uuid.UUID,
        voice_engine: str = "edge_tts",
        voice_id: str = "en-US-ChristopherNeural",
        avatar_engine: str = "programmatic",
        avatar_model_id: str | None = None,
        primary_hex: str = "#1E40AF",
        accent_hex: str = "#F59E0B",
        subtitle_highlight_hex: str = "#10B981",
        background_hex: str = "#0F172A",
        watermark_logo_url: str | None = None,
        intro_bumper_url: str | None = None,
        outro_bumper_url: str | None = None,
        font_family: str = "Arial",
    ) -> ClientBrandKit:
        existing = self.get_by_client_id(client_id)
        if existing:
            existing.voice_engine = voice_engine
            existing.voice_id = voice_id
            existing.avatar_engine = avatar_engine
            existing.avatar_model_id = avatar_model_id
            existing.primary_hex = primary_hex
            existing.accent_hex = accent_hex
            existing.subtitle_highlight_hex = subtitle_highlight_hex
            existing.background_hex = background_hex
            existing.watermark_logo_url = watermark_logo_url
            existing.intro_bumper_url = intro_bumper_url
            existing.outro_bumper_url = outro_bumper_url
            existing.font_family = font_family
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        kit = ClientBrandKit(
            client_id=client_id,
            voice_engine=voice_engine,
            voice_id=voice_id,
            avatar_engine=avatar_engine,
            avatar_model_id=avatar_model_id,
            primary_hex=primary_hex,
            accent_hex=accent_hex,
            subtitle_highlight_hex=subtitle_highlight_hex,
            background_hex=background_hex,
            watermark_logo_url=watermark_logo_url,
            intro_bumper_url=intro_bumper_url,
            outro_bumper_url=outro_bumper_url,
            font_family=font_family,
        )
        self.session.add(kit)
        self.session.commit()
        self.session.refresh(kit)
        return kit
