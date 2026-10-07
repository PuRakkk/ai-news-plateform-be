import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# --- Persona Schemas ---
class ClientPersonaBase(BaseModel):
    persona_role: str = "AI Chief of Staff"
    tone_of_voice: str = "Concise, analytical, authoritative"
    target_audience: str = "Business owners, tech executives, and startup founders"
    default_cta: str = "Follow for daily executive AI updates."


class ClientPersonaCreate(ClientPersonaBase):
    pass


class ClientPersonaUpdate(BaseModel):
    persona_role: str | None = None
    tone_of_voice: str | None = None
    target_audience: str | None = None
    default_cta: str | None = None


class ClientPersonaRead(ClientPersonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID


# --- Topic Filter Schemas ---
class ClientTopicFilterBase(BaseModel):
    industries: str = "[]"
    focus_keywords: str = "[]"
    excluded_keywords: str = "[]"
    weight_actionability: float = 0.40
    weight_economic: float = 0.30
    weight_regulatory: float = 0.20
    weight_novelty: float = 0.10


class ClientTopicFilterCreate(ClientTopicFilterBase):
    pass


class ClientTopicFilterUpdate(BaseModel):
    industries: str | None = None
    focus_keywords: str | None = None
    excluded_keywords: str | None = None
    weight_actionability: float | None = None
    weight_economic: float | None = None
    weight_regulatory: float | None = None
    weight_novelty: float | None = None


class ClientTopicFilterRead(ClientTopicFilterBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID


# --- Brand Kit Schemas ---
class ClientBrandKitBase(BaseModel):
    voice_engine: str = "edge_tts"
    voice_id: str = "en-US-ChristopherNeural"
    avatar_engine: str = "programmatic"
    avatar_model_id: str | None = None
    primary_hex: str = "#1E40AF"
    accent_hex: str = "#F59E0B"
    subtitle_highlight_hex: str = "#10B981"
    background_hex: str = "#0F172A"
    watermark_logo_url: str | None = None
    intro_bumper_url: str | None = None
    outro_bumper_url: str | None = None
    font_family: str = "Arial"


class ClientBrandKitCreate(ClientBrandKitBase):
    pass


class ClientBrandKitUpdate(BaseModel):
    voice_engine: str | None = None
    voice_id: str | None = None
    avatar_engine: str | None = None
    avatar_model_id: str | None = None
    primary_hex: str | None = None
    accent_hex: str | None = None
    subtitle_highlight_hex: str | None = None
    background_hex: str | None = None
    watermark_logo_url: str | None = None
    intro_bumper_url: str | None = None
    outro_bumper_url: str | None = None
    font_family: str | None = None


class ClientBrandKitRead(ClientBrandKitBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID


# --- Profile Schemas ---
class ClientProfileBase(BaseModel):
    name: str
    slug: str
    is_active: bool = True


class ClientProfileCreate(ClientProfileBase):
    persona: ClientPersonaCreate | None = None
    topic_filter: ClientTopicFilterCreate | None = None
    brand_kit: ClientBrandKitCreate | None = None


class ClientProfileUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    is_active: bool | None = None


class ClientProfileRead(ClientProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClientDetailRead(ClientProfileRead):
    persona: ClientPersonaRead | None = None
    topic_filter: ClientTopicFilterRead | None = None
    brand_kit: ClientBrandKitRead | None = None
