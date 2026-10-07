import uuid
from datetime import datetime
from typing import Any, Optional
from sqlmodel import Field, Relationship, SQLModel

from app.models.client import ClientProfile
from app.models.news import Article, utc_now


class Script(SQLModel, table=True):
    """Grounded short-form video script."""

    __tablename__ = "script"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    article_id: uuid.UUID = Field(foreign_key="article.id", index=True)
    client_id: uuid.UUID | None = Field(default=None, foreign_key="client_profile.id", index=True)
    title: str = Field(default="")
    persona_role: str = Field(default="AI Chief of Staff")
    total_estimated_duration_sec: int = Field(default=75)
    call_to_action: str = Field(default="")
    status: str = Field(default="draft", index=True)  # draft, audited, approved, rejected
    created_at: datetime = Field(default_factory=utc_now, index=True)

    article: Optional[Article] = Relationship()
    client: Optional[ClientProfile] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        art_title = self.article.title[:45] if self.article else (self.title[:45] or "Script")
        c_name = self.client.name if self.client else "Default Profile"
        return f"{art_title} ({c_name}) [{self.status}]"

    def __str__(self) -> str:
        return self.title or "Script"


class ScriptBeat(SQLModel, table=True):
    """Individual segment in the 5-beat short-form script."""

    __tablename__ = "script_beat"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    script_id: uuid.UUID = Field(foreign_key="script.id", index=True)
    beat_index: int = Field(index=True)  # 1 to 5
    beat_type: str = Field(index=True)  # HOOK, CONTEXT, CORE_SHIFT, BUSINESS_IMPACT, CTA
    spoken_script: str  # Exact teleprompter spoken text
    visual_directive: str  # e.g., "PRESENTER_CAMERA_A", "PRESENTER_CAMERA_B_SPLIT"
    whiteboard_directive: str | None = Field(default=None)  # Diagram or bullet description for motion graphics
    estimated_seconds: int = Field(default=15)

    script: Optional[Script] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        s_title = self.script.title[:30] if self.script else "Script"
        return f"Beat {self.beat_index} ({self.beat_type}) - {s_title}"

    def __str__(self) -> str:
        return f"Beat {self.beat_index} ({self.beat_type})"


class ScriptClaimAudit(SQLModel, table=True):
    """Claim-by-claim factual grounding verification record."""

    __tablename__ = "script_claim_audit"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    script_id: uuid.UUID = Field(foreign_key="script.id", index=True)
    beat_index: int = Field(index=True)
    claim_text: str  # Atomic factual assertion extracted from script
    verified_citation: str | None = Field(default=None)  # Source article section or paragraph
    source_verbatim_quote: str | None = Field(default=None)  # Direct quote from article confirming claim
    is_grounded: bool = Field(default=False, index=True)  # True if backed by source quote
    audit_notes: str | None = Field(default=None)

    script: Optional[Script] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        badge = "Grounded" if self.is_grounded else "UNGROUNDED"
        return f"[{badge}] Beat {self.beat_index}: {self.claim_text[:40]}"

    def __str__(self) -> str:
        return self.claim_text
