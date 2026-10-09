import uuid
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models.news import Article, ArticleScore, ArticleVerification, NewsSource
from app.repositories.base import BaseRepository

DEFAULT_SOURCES: list[dict[str, str | int]] = [
    {
        "name": "TechCrunch AI",
        "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "The Verge AI",
        "feed_url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "Wired AI",
        "feed_url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "Ars Technica Tech",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "VentureBeat AI",
        "feed_url": "https://venturebeat.com/category/ai/feed/",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "MIT Technology Review",
        "feed_url": "https://www.technologyreview.com/feed/",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "Google DeepMind Blog",
        "feed_url": "https://deepmind.google/blog/rss.xml",
        "feed_type": "rss",
        "trust_tier": 1,
    },
    {
        "name": "OpenAI Newsroom",
        "feed_url": "https://openai.com/news/rss.xml",
        "feed_type": "rss",
        "trust_tier": 1,
    },
]


class NewsSourceRepository(BaseRepository[NewsSource]):
    def __init__(self, session: Session) -> None:
        super().__init__(NewsSource, session)

    def get_by_feed_url(self, feed_url: str) -> NewsSource | None:
        statement = select(NewsSource).where(NewsSource.feed_url == feed_url)
        return self.session.exec(statement).first()

    def get_active_sources(self) -> list[NewsSource]:
        statement = select(NewsSource).where(NewsSource.is_active == True)  # noqa: E712
        return list(self.session.exec(statement).all())

    def seed_default_sources(self) -> list[NewsSource]:
        seeded: list[NewsSource] = []
        for src in DEFAULT_SOURCES:
            existing = self.get_by_feed_url(str(src["feed_url"]))
            if not existing:
                new_src = NewsSource(
                    name=str(src["name"]),
                    feed_url=str(src["feed_url"]),
                    feed_type=str(src["feed_type"]),
                    trust_tier=int(src["trust_tier"]),
                    is_active=True,
                )
                self.session.add(new_src)
                seeded.append(new_src)
        if seeded:
            self.session.commit()
            for s in seeded:
                self.session.refresh(s)
        return seeded


class ArticleRepository(BaseRepository[Article]):
    def __init__(self, session: Session) -> None:
        super().__init__(Article, session)

    def get_by_url(self, url: str) -> Article | None:
        statement = select(Article).where(Article.url == url)
        return self.session.exec(statement).first()

    def get_by_content_hash(self, content_hash: str) -> Article | None:
        statement = select(Article).where(Article.content_hash == content_hash)
        return self.session.exec(statement).first()

    def create_if_not_exists(self, article: Article) -> tuple[Article, bool]:
        """Idempotently insert an article checking URL and SHA-256 content hash."""
        existing = self.get_by_url(article.url)
        if existing:
            return existing, False

        existing_hash = self.get_by_content_hash(article.content_hash)
        if existing_hash:
            return existing_hash, False

        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        return article, True

    def get_recent_articles(self, limit: int = 50) -> list[Article]:
        statement = (
            select(Article)
            .order_by(Article.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def update_status(self, article_id: uuid.UUID, status: str) -> Article | None:
        article = self.session.get(Article, article_id)
        if not article:
            return None
        article.status = status
        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        return article

    def update_full_text(self, article_id: uuid.UUID, full_text: str) -> Article | None:
        article = self.session.get(Article, article_id)
        if not article:
            return None
        article.full_text = full_text
        self.session.add(article)
        self.session.commit()
        self.session.refresh(article)
        return article


class ArticleVerificationRepository(BaseRepository[ArticleVerification]):
    def __init__(self, session: Session) -> None:
        super().__init__(ArticleVerification, session)

    def get_by_article_id(self, article_id: uuid.UUID) -> ArticleVerification | None:
        statement = select(ArticleVerification).where(ArticleVerification.article_id == article_id)
        return self.session.exec(statement).first()

    def upsert_verification(self, verification: ArticleVerification) -> ArticleVerification:
        existing = self.get_by_article_id(verification.article_id)
        if existing:
            existing.secondary_url = verification.secondary_url
            existing.secondary_source = verification.secondary_source
            existing.agreement_score = verification.agreement_score
            existing.corroboration_notes = verification.corroboration_notes
            existing.is_verified = verification.is_verified
            existing.checked_at = datetime.now(timezone.utc)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        self.session.add(verification)
        self.session.commit()
        self.session.refresh(verification)
        return verification


class ArticleScoreRepository(BaseRepository[ArticleScore]):
    def __init__(self, session: Session) -> None:
        super().__init__(ArticleScore, session)

    def get_by_article_id(
        self, article_id: uuid.UUID, client_id: uuid.UUID | None = None
    ) -> ArticleScore | None:
        statement = select(ArticleScore).where(
            ArticleScore.article_id == article_id, ArticleScore.client_id == client_id
        )
        return self.session.exec(statement).first()

    def upsert_score(self, score: ArticleScore) -> ArticleScore:
        existing = self.get_by_article_id(score.article_id, score.client_id)
        if existing:
            existing.composite_score = score.composite_score
            existing.actionability = score.actionability
            existing.economic_impact = score.economic_impact
            existing.regulatory_impact = score.regulatory_impact
            existing.novelty = score.novelty
            existing.reasoning = score.reasoning
            existing.is_selected = score.is_selected
            existing.scored_at = datetime.now(timezone.utc)
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        self.session.add(score)
        self.session.commit()
        self.session.refresh(score)
        return score

    def get_winning_article(
        self, client_id: uuid.UUID | None = None
    ) -> ArticleScore | None:
        """Retrieve the currently elected winning article score for a given client (or default)."""
        statement = (
            select(ArticleScore)
            .where(
                ArticleScore.client_id == client_id,
                ArticleScore.is_selected == True,  # noqa: E712
            )
            .order_by(ArticleScore.scored_at.desc())
        )
        return self.session.exec(statement).first()

    def set_winning_article(
        self, article_id: uuid.UUID, client_id: uuid.UUID | None = None
    ) -> ArticleScore | None:
        """Mark this article as the elected winner, unsetting any previous selections for the scope."""
        # Unset previous selected
        statement = select(ArticleScore).where(
            ArticleScore.client_id == client_id, ArticleScore.is_selected == True  # noqa: E712
        )
        previous_winners = self.session.exec(statement).all()
        for p in previous_winners:
            p.is_selected = False
            self.session.add(p)

        target = self.get_by_article_id(article_id, client_id)
        if target:
            target.is_selected = True
            self.session.add(target)
            self.session.commit()
            self.session.refresh(target)
            return target

        self.session.commit()
        return None

