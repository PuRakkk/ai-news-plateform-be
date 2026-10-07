import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# --- Beat Schemas ---
class ScriptBeatBase(BaseModel):
    beat_index: int = Field(ge=1, le=5)
    beat_type: str  # HOOK, CONTEXT, CORE_SHIFT, BUSINESS_IMPACT, CTA
    spoken_script: str
    visual_directive: str
    whiteboard_directive: str | None = None
    estimated_seconds: int = 15


class ScriptBeatCreate(ScriptBeatBase):
    pass


class ScriptBeatRead(ScriptBeatBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    script_id: uuid.UUID


# --- Claim Audit Schemas ---
class ScriptClaimAuditBase(BaseModel):
    beat_index: int = Field(ge=1, le=5)
    claim_text: str
    verified_citation: str | None = None
    source_verbatim_quote: str | None = None
    is_grounded: bool = False
    audit_notes: str | None = None


class ScriptClaimAuditCreate(ScriptClaimAuditBase):
    pass


class ScriptClaimAuditRead(ScriptClaimAuditBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    script_id: uuid.UUID


# --- Script Schemas ---
class ScriptBase(BaseModel):
    article_id: uuid.UUID
    client_id: uuid.UUID | None = None
    title: str = ""
    persona_role: str = "AI Chief of Staff"
    total_estimated_duration_sec: int = 75
    call_to_action: str = ""
    status: str = "draft"  # draft, audited, approved, rejected


class ScriptCreate(ScriptBase):
    beats: list[ScriptBeatCreate] = []


class ScriptRead(ScriptBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ScriptGroundingSummary(BaseModel):
    total_claims: int = 0
    grounded_claims: int = 0
    grounding_ratio: float = 0.0
    is_fully_grounded: bool = False


class ScriptDetailRead(ScriptRead):
    beats: list[ScriptBeatRead] = []
    audits: list[ScriptClaimAuditRead] = []
    grounding_summary: ScriptGroundingSummary | None = None


# --- Generation Request / Response Schemas ---
class ScriptGenerationRequest(BaseModel):
    article_id: uuid.UUID
    client_id: uuid.UUID | None = None
    auto_audit: bool = True
    enforce_grounding_revision: bool = True


class ScriptGenerationResultDTO(BaseModel):
    script: ScriptDetailRead
    message: str = "Script generated and audited successfully."
