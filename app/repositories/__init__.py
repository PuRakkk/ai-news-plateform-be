"""Data access repositories."""
from app.repositories.base import BaseRepository
from app.repositories.client_repo import (
    ClientBrandKitRepository,
    ClientPersonaRepository,
    ClientProfileRepository,
    ClientTopicFilterRepository,
)
from app.repositories.media_repo import RenderedVideoRepository
from app.repositories.news_repo import (
    ArticleRepository,
    ArticleScoreRepository,
    ArticleVerificationRepository,
    NewsSourceRepository,
)
from app.repositories.script_repo import (
    ScriptBeatRepository,
    ScriptClaimAuditRepository,
    ScriptRepository,
)

__all__ = [
    "BaseRepository",
    "NewsSourceRepository",
    "ArticleRepository",
    "ArticleVerificationRepository",
    "ArticleScoreRepository",
    "ClientProfileRepository",
    "ClientPersonaRepository",
    "ClientTopicFilterRepository",
    "ClientBrandKitRepository",
    "ScriptRepository",
    "ScriptBeatRepository",
    "ScriptClaimAuditRepository",
    "RenderedVideoRepository",
]
