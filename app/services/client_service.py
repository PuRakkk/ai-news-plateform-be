import json
import uuid
from sqlmodel import Session

from app.models.client import ClientBrandKit, ClientPersona, ClientProfile, ClientTopicFilter
from app.repositories.client_repo import (
    ClientBrandKitRepository,
    ClientPersonaRepository,
    ClientProfileRepository,
    ClientTopicFilterRepository,
)
from app.schemas.client import (
    ClientBrandKitRead,
    ClientBrandKitUpdate,
    ClientDetailRead,
    ClientPersonaRead,
    ClientPersonaUpdate,
    ClientProfileCreate,
    ClientProfileRead,
    ClientTopicFilterRead,
    ClientTopicFilterUpdate,
)


class ClientService:
    """Business service for client profile and persona management."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.profile_repo = ClientProfileRepository(session)
        self.persona_repo = ClientPersonaRepository(session)
        self.topic_repo = ClientTopicFilterRepository(session)
        self.brand_repo = ClientBrandKitRepository(session)

    def create_client(self, payload: ClientProfileCreate) -> ClientDetailRead:
        profile = self.profile_repo.create_client(
            name=payload.name,
            slug=payload.slug,
            is_active=payload.is_active,
        )

        persona_record: ClientPersona | None = None
        if payload.persona:
            persona_record = self.persona_repo.upsert_persona(
                client_id=profile.id,
                persona_role=payload.persona.persona_role,
                tone_of_voice=payload.persona.tone_of_voice,
                target_audience=payload.persona.target_audience,
                default_cta=payload.persona.default_cta,
            )
        else:
            persona_record = self.persona_repo.upsert_persona(client_id=profile.id)

        topic_record: ClientTopicFilter | None = None
        if payload.topic_filter:
            topic_record = self.topic_repo.upsert_topic_filter(
                client_id=profile.id,
                industries=payload.topic_filter.industries,
                focus_keywords=payload.topic_filter.focus_keywords,
                excluded_keywords=payload.topic_filter.excluded_keywords,
                weight_actionability=payload.topic_filter.weight_actionability,
                weight_economic=payload.topic_filter.weight_economic,
                weight_regulatory=payload.topic_filter.weight_regulatory,
                weight_novelty=payload.topic_filter.weight_novelty,
            )
        else:
            topic_record = self.topic_repo.upsert_topic_filter(client_id=profile.id)

        brand_record: ClientBrandKit | None = None
        if payload.brand_kit:
            brand_record = self.brand_repo.upsert_brand_kit(
                client_id=profile.id,
                voice_engine=payload.brand_kit.voice_engine,
                voice_id=payload.brand_kit.voice_id,
                avatar_engine=payload.brand_kit.avatar_engine,
                avatar_model_id=payload.brand_kit.avatar_model_id,
                primary_hex=payload.brand_kit.primary_hex,
                accent_hex=payload.brand_kit.accent_hex,
                subtitle_highlight_hex=payload.brand_kit.subtitle_highlight_hex,
                background_hex=payload.brand_kit.background_hex,
                watermark_logo_url=payload.brand_kit.watermark_logo_url,
                intro_bumper_url=payload.brand_kit.intro_bumper_url,
                outro_bumper_url=payload.brand_kit.outro_bumper_url,
                font_family=payload.brand_kit.font_family,
            )
        else:
            brand_record = self.brand_repo.upsert_brand_kit(client_id=profile.id)

        return ClientDetailRead(
            id=profile.id,
            name=profile.name,
            slug=profile.slug,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            persona=ClientPersonaRead.model_validate(persona_record) if persona_record else None,
            topic_filter=ClientTopicFilterRead.model_validate(topic_record) if topic_record else None,
            brand_kit=ClientBrandKitRead.model_validate(brand_record) if brand_record else None,
        )

    def list_clients(self) -> list[ClientProfileRead]:
        clients = self.profile_repo.get_active_clients()
        return [ClientProfileRead.model_validate(c) for c in clients]

    def get_client_detail(self, client_id: uuid.UUID) -> ClientDetailRead | None:
        profile, persona, topic_filter = self.profile_repo.get_client_bundle(client_id)
        if not profile:
            return None

        brand_kit = self.brand_repo.get_by_client_id(client_id)

        return ClientDetailRead(
            id=profile.id,
            name=profile.name,
            slug=profile.slug,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            persona=ClientPersonaRead.model_validate(persona) if persona else None,
            topic_filter=ClientTopicFilterRead.model_validate(topic_filter) if topic_filter else None,
            brand_kit=ClientBrandKitRead.model_validate(brand_kit) if brand_kit else None,
        )

    def update_persona(self, client_id: uuid.UUID, update_data: ClientPersonaUpdate) -> ClientPersonaRead | None:
        client = self.profile_repo.get_by_id(client_id)
        if not client:
            return None

        current = self.persona_repo.get_by_client_id(client_id)
        role = update_data.persona_role if update_data.persona_role is not None else (current.persona_role if current else "AI Chief of Staff")
        tone = update_data.tone_of_voice if update_data.tone_of_voice is not None else (current.tone_of_voice if current else "Concise, analytical")
        audience = update_data.target_audience if update_data.target_audience is not None else (current.target_audience if current else "Executives")
        cta = update_data.default_cta if update_data.default_cta is not None else (current.default_cta if current else "Follow for updates.")

        updated = self.persona_repo.upsert_persona(
            client_id=client_id,
            persona_role=role,
            tone_of_voice=tone,
            target_audience=audience,
            default_cta=cta,
        )
        return ClientPersonaRead.model_validate(updated)

    def update_topic_filter(
        self, client_id: uuid.UUID, update_data: ClientTopicFilterUpdate
    ) -> ClientTopicFilterRead | None:
        client = self.profile_repo.get_by_id(client_id)
        if not client:
            return None

        current = self.topic_repo.get_by_client_id(client_id)
        industries = update_data.industries if update_data.industries is not None else (current.industries if current else "[]")
        focus = update_data.focus_keywords if update_data.focus_keywords is not None else (current.focus_keywords if current else "[]")
        excluded = update_data.excluded_keywords if update_data.excluded_keywords is not None else (current.excluded_keywords if current else "[]")
        w_act = update_data.weight_actionability if update_data.weight_actionability is not None else (current.weight_actionability if current else 0.40)
        w_eco = update_data.weight_economic if update_data.weight_economic is not None else (current.weight_economic if current else 0.30)
        w_reg = update_data.weight_regulatory if update_data.weight_regulatory is not None else (current.weight_regulatory if current else 0.20)
        w_nov = update_data.weight_novelty if update_data.weight_novelty is not None else (current.weight_novelty if current else 0.10)

        updated = self.topic_repo.upsert_topic_filter(
            client_id=client_id,
            industries=industries,
            focus_keywords=focus,
            excluded_keywords=excluded,
            weight_actionability=w_act,
            weight_economic=w_eco,
            weight_regulatory=w_reg,
            weight_novelty=w_nov,
        )
        return ClientTopicFilterRead.model_validate(updated)

    def update_brand_kit(
        self, client_id: uuid.UUID, update_data: ClientBrandKitUpdate
    ) -> ClientBrandKitRead | None:
        client = self.profile_repo.get_by_id(client_id)
        if not client:
            return None

        current = self.brand_repo.get_by_client_id(client_id)
        voice_engine = update_data.voice_engine if update_data.voice_engine is not None else (current.voice_engine if current else "edge_tts")
        voice_id = update_data.voice_id if update_data.voice_id is not None else (current.voice_id if current else "en-AU-NatashaNeural")
        avatar_engine = update_data.avatar_engine if update_data.avatar_engine is not None else (current.avatar_engine if current else "programmatic")
        avatar_model_id = update_data.avatar_model_id if update_data.avatar_model_id is not None else (current.avatar_model_id if current else None)
        primary_hex = update_data.primary_hex if update_data.primary_hex is not None else (current.primary_hex if current else "#D9381E")
        accent_hex = update_data.accent_hex if update_data.accent_hex is not None else (current.accent_hex if current else "#F59E0B")
        sub_hex = update_data.subtitle_highlight_hex if update_data.subtitle_highlight_hex is not None else (current.subtitle_highlight_hex if current else "#10B981")
        bg_hex = update_data.background_hex if update_data.background_hex is not None else (current.background_hex if current else "#0D192F")
        watermark = update_data.watermark_logo_url if update_data.watermark_logo_url is not None else (current.watermark_logo_url if current else None)
        intro_bumper = update_data.intro_bumper_url if update_data.intro_bumper_url is not None else (current.intro_bumper_url if current else None)
        outro_bumper = update_data.outro_bumper_url if update_data.outro_bumper_url is not None else (current.outro_bumper_url if current else None)
        font = update_data.font_family if update_data.font_family is not None else (current.font_family if current else "Arial")

        updated = self.brand_repo.upsert_brand_kit(
            client_id=client_id,
            voice_engine=voice_engine,
            voice_id=voice_id,
            avatar_engine=avatar_engine,
            avatar_model_id=avatar_model_id,
            primary_hex=primary_hex,
            accent_hex=accent_hex,
            subtitle_highlight_hex=sub_hex,
            background_hex=bg_hex,
            watermark_logo_url=watermark,
            intro_bumper_url=intro_bumper,
            outro_bumper_url=outro_bumper,
            font_family=font,
        )
        return ClientBrandKitRead.model_validate(updated)
