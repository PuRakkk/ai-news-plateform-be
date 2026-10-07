"""SQLModel database models registry."""
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile, ClientTopicFilter
from app.models.media import RenderedVideo
from app.models.news import Article, ArticleScore, ArticleVerification, NewsSource
from app.models.script import Script, ScriptBeat, ScriptClaimAudit

__all__: list[str] = [
    "NewsSource",
    "Article",
    "ArticleVerification",
    "ArticleScore",
    "ClientProfile",
    "ClientPersona",
    "ClientTopicFilter",
    "ClientBrandKit",
    "Script",
    "ScriptBeat",
    "ScriptClaimAudit",
    "RenderedVideo",
]
