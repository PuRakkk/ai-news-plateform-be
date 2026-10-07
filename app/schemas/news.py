import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NewsSourceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    feed_url: str = Field(..., max_length=500)
    feed_type: str = Field(default="rss", max_length=50)
    trust_tier: int = Field(default=1, ge=1, le=5)
    is_active: bool = True


class NewsSourceCreate(NewsSourceBase):
    pass


class NewsSourceRead(NewsSourceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    url: str = Field(..., max_length=1000)
    summary: str | None = None
    full_text: str | None = None
    published_at: datetime | None = None


class ArticleCreate(ArticleBase):
    source_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    content_hash: str


class ArticleRead(ArticleBase):
    id: uuid.UUID
    source_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleVerificationRead(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    secondary_url: str | None = None
    secondary_source: str | None = None
    agreement_score: float
    corroboration_notes: str | None = None
    is_verified: bool
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleScoreRead(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    client_id: uuid.UUID | None = None
    composite_score: float
    actionability: float
    economic_impact: float
    regulatory_impact: float
    novelty: float
    reasoning: str | None = None
    is_selected: bool
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleDetailRead(ArticleRead):
    content_hash: str
    verification: ArticleVerificationRead | None = None
    score: ArticleScoreRead | None = None


class ScreenedCandidateDTO(BaseModel):
    title: str
    url: str
    summary: str | None = None
    relevance_score: float
    screening_reason: str


class IngestionSummaryDTO(BaseModel):
    sources_checked: int
    articles_ingested: int
    candidates_screened: int
    candidates_verified: int
    winning_article_id: uuid.UUID | None = None
    winning_article_title: str | None = None
    winning_composite_score: float = 0.0
    client_winners: dict[str, uuid.UUID] = Field(default_factory=dict)
