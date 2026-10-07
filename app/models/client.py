import uuid
from datetime import datetime
from typing import Any, Optional
from sqlmodel import Field, Relationship, SQLModel

from app.models.news import utc_now


class ClientProfile(SQLModel, table=True):
    """Business owner or brand root tenant entity."""

    __tablename__ = "client_profile"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)  # e.g., "Apex Logistics AI", "John Doe Media"
    slug: str = Field(unique=True, index=True)  # e.g., "apex-logistics"
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def __admin_repr__(self, request: Any = None) -> str:
        return f"{self.name} ({self.slug})"

    def __str__(self) -> str:
        return self.name


class ClientPersona(SQLModel, table=True):
    """Editorial voice, target audience, and call-to-action for a business owner."""

    __tablename__ = "client_persona"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="client_profile.id", unique=True, index=True)
    persona_role: str = Field(default="AI Chief of Staff")  # e.g., "Pragmatic CTO", "Supply Chain AI Specialist"
    tone_of_voice: str = Field(default="Concise, analytical, authoritative")
    target_audience: str = Field(default="Business owners, tech executives, and startup founders")
    default_cta: str = Field(default="Follow for daily executive AI updates.")

    client: Optional[ClientProfile] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        c_name = self.client.name if self.client else "Client"
        return f"{self.persona_role} [{c_name}]"

    def __str__(self) -> str:
        return self.persona_role


class ClientTopicFilter(SQLModel, table=True):
    """Industry preferences, focus topics, and scoring weight modifiers."""

    __tablename__ = "client_topic_filter"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="client_profile.id", unique=True, index=True)
    industries: str = Field(default="[]")  # JSON list: e.g. ["logistics", "automation"]
    focus_keywords: str = Field(default="[]")  # JSON list: e.g. ["autonomous fleet", "warehouse robotics"]
    excluded_keywords: str = Field(default="[]")  # JSON list: e.g. ["crypto", "gaming"]
    weight_actionability: float = Field(default=0.40)
    weight_economic: float = Field(default=0.30)
    weight_regulatory: float = Field(default=0.20)
    weight_novelty: float = Field(default=0.10)

    client: Optional[ClientProfile] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        c_name = self.client.name if self.client else "Client"
        return f"Topic Filter [{c_name}]"

    def __str__(self) -> str:
        return f"Topic Filter [{self.client_id}]"


class ClientBrandKit(SQLModel, table=True):
    """Visual branding, voice identity, and motion packaging configuration."""

    __tablename__ = "client_brand_kit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="client_profile.id", unique=True, index=True)
    voice_engine: str = Field(default="edge_tts")  # edge_tts, elevenlabs, mock
    voice_id: str = Field(default="en-US-ChristopherNeural")  # natural executive tone
    avatar_engine: str = Field(default="programmatic")  # programmatic, mock, heygen, did
    avatar_model_id: str | None = Field(default=None)
    primary_hex: str = Field(default="#1E40AF")
    accent_hex: str = Field(default="#F59E0B")
    subtitle_highlight_hex: str = Field(default="#10B981")
    background_hex: str = Field(default="#0F172A")
    watermark_logo_url: str | None = Field(default=None)
    intro_bumper_url: str | None = Field(default=None)
    outro_bumper_url: str | None = Field(default=None)
    font_family: str = Field(default="Arial")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    client: Optional[ClientProfile] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        c_name = self.client.name if self.client else "Client"
        return f"Brand Kit [{c_name}]"

    def __str__(self) -> str:
        return f"Brand Kit [{self.client_id}]"
