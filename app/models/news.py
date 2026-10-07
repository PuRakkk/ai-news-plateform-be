import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.client import ClientProfile


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class NewsSource(SQLModel, table=True):
    """Catalog of authoritative news and research feed sources."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    feed_url: str = Field(unique=True, index=True)
    feed_type: str = Field(default="rss")  # "rss", "web_sweep"
    trust_tier: int = Field(default=1)  # 1 = primary lab / authority wire, 2 = secondary
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def __admin_repr__(self, request: Any = None) -> str:
        return f"{self.name} (Tier {self.trust_tier})"

    def __str__(self) -> str:
        return self.name


class Article(SQLModel, table=True):
    """Raw and processed news articles ingested into the shared news lake."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID | None = Field(default=None, foreign_key="newssource.id", index=True)
    client_id: uuid.UUID | None = Field(default=None, foreign_key="client_profile.id", index=True)
    url: str = Field(unique=True, index=True)
    title: str = Field(index=True)
    summary: str | None = Field(default=None)
    full_text: str | None = Field(default=None)
    content_hash: str = Field(index=True)  # SHA-256 for deduplication
    published_at: datetime | None = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)  # pending, screened, verified, rejected, selected
    created_at: datetime = Field(default_factory=utc_now, index=True)

    source: Optional[NewsSource] = Relationship()
    client: Optional["ClientProfile"] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        short = self.title[:45] + "..." if len(self.title) > 45 else self.title
        c_label = f" ({self.client.name})" if self.client else ""
        return f"{short}{c_label} [{self.status}]"

    def __str__(self) -> str:
        return self.title


class ArticleVerification(SQLModel, table=True):
    """Dual-source cross-check and factual corroboration records."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    article_id: uuid.UUID = Field(foreign_key="article.id", unique=True, index=True)
    secondary_url: str | None = Field(default=None)
    secondary_source: str | None = Field(default=None)
    agreement_score: float = Field(default=0.0)  # 0.00 to 1.00
    corroboration_notes: str | None = Field(default=None)
    is_verified: bool = Field(default=False, index=True)
    checked_at: datetime = Field(default_factory=utc_now)

    article: Optional[Article] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        art_title = self.article.title[:45] if self.article else str(self.article_id)[:8]
        status_badge = "Verified" if self.is_verified else "Unverified"
        return f"[{status_badge}] {art_title}"

    def __str__(self) -> str:
        return f"Verification for {self.article_id}"


class ArticleScore(SQLModel, table=True):
    """Two-stage business utility and client relevance scoring."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    article_id: uuid.UUID = Field(foreign_key="article.id", index=True)
    client_id: uuid.UUID | None = Field(default=None, index=True)  # None for default baseline profile
    composite_score: float = Field(default=0.0, index=True)
    actionability: float = Field(default=0.0)  # Weight: 40%
    economic_impact: float = Field(default=0.0)  # Weight: 30%
    regulatory_impact: float = Field(default=0.0)  # Weight: 20%
    novelty: float = Field(default=0.0)  # Weight: 10%
    reasoning: str | None = Field(default=None)
    is_selected: bool = Field(default=False, index=True)
    scored_at: datetime = Field(default_factory=utc_now)

    article: Optional[Article] = Relationship()

    def __admin_repr__(self, request: Any = None) -> str:
        art_title = self.article.title[:45] if self.article else str(self.article_id)[:8]
        selected_badge = " [WINNER]" if self.is_selected else ""
        return f"Score {self.composite_score:.2f}{selected_badge} - {art_title}"

    def __str__(self) -> str:
        return f"Score: {self.composite_score:.2f}"
