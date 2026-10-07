import json
import uuid
from sqlmodel import Session

from app.models.client import ClientPersona, ClientProfile, ClientTopicFilter
from app.repositories.client_repo import (
    ClientPersonaRepository,
    ClientProfileRepository,
    ClientTopicFilterRepository,
)
from app.schemas.client import (
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

        return ClientDetailRead(
            id=profile.id,
            name=profile.name,
            slug=profile.slug,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            persona=ClientPersonaRead.model_validate(persona_record) if persona_record else None,
            topic_filter=ClientTopicFilterRead.model_validate(topic_record) if topic_record else None,
        )

    def list_clients(self) -> list[ClientProfileRead]:
        clients = self.profile_repo.get_active_clients()
        return [ClientProfileRead.model_validate(c) for c in clients]

    def get_client_detail(self, client_id: uuid.UUID) -> ClientDetailRead | None:
        profile, persona, topic_filter = self.profile_repo.get_client_bundle(client_id)
        if not profile:
            return None

        return ClientDetailRead(
            id=profile.id,
            name=profile.name,
            slug=profile.slug,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            persona=ClientPersonaRead.model_validate(persona) if persona else None,
            topic_filter=ClientTopicFilterRead.model_validate(topic_filter) if topic_filter else None,
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
