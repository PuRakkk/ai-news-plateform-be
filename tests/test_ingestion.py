import uuid
from typing import Any
import pytest
from starlette.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine
from app.models.news import Article, ArticleScore, ArticleVerification, NewsSource
from app.repositories.news_repo import (
    ArticleRepository,
    ArticleScoreRepository,
    ArticleVerificationRepository,
    NewsSourceRepository,
)
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.rss_fetcher import compute_article_hash
from app.services.ingestion.text_extractor import clean_html_to_text
from app.services.ingestion.verifier import extract_root_domain, is_domain_independent
from app.services.llm.base import LLMProviderAdapter


class MockLLMProvider(LLMProviderAdapter):
    """Mock LLM adapter for deterministic unit testing without external API calls."""

    async def screen_candidates(
        self,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
        topic_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "article_id": str(c["id"]),
                "title": c["title"],
                "url": c.get("url", ""),
                "relevance_score": 0.95,
                "screening_reason": "Highly relevant AI breakthrough.",
            }
            for c in candidates[:top_k]
        ]

    async def verify_corroboration(
        self,
        primary_title: str,
        primary_text: str,
        secondary_title: str,
        secondary_text: str,
    ) -> dict[str, Any]:
        return {
            "agreement_score": 0.88,
            "is_verified": True,
            "corroboration_notes": "Both articles corroborate the benchmark results and pricing.",
        }

    async def score_utility(
        self,
        title: str,
        full_text: str,
        profile_criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "composite_score": 0.85,
            "actionability": 0.90,
            "economic_impact": 0.85,
            "regulatory_impact": 0.70,
            "novelty": 0.90,
            "reasoning": "Major foundation model release with dramatic inference cost reductions.",
        }

    async def generate_script(
        self,
        article_title: str,
        full_text: str,
        persona: dict[str, Any],
        topic_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "title": article_title,
            "persona_role": persona.get("persona_role", "AI Chief of Staff"),
            "total_estimated_duration_sec": 75,
            "call_to_action": persona.get("default_cta", "Follow for daily AI updates."),
            "beats": [],
        }

    async def audit_claims(
        self, beats: list[dict[str, Any]], full_text: str
    ) -> list[dict[str, Any]]:
        return []

    async def revise_script_beat(
        self,
        beat: dict[str, Any],
        ungrounded_claims: list[dict[str, Any]],
        full_text: str,
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        return beat



def test_article_hash_determinism() -> None:
    h1 = compute_article_hash("https://example.com/ai-1", "New Model Released")
    h2 = compute_article_hash("https://example.com/ai-1", "New Model Released")
    h3 = compute_article_hash("https://example.com/ai-2", "New Model Released")
    assert h1 == h2
    assert h1 != h3


def test_domain_independence() -> None:
    assert extract_root_domain("https://techcrunch.com/2026/openai") == "techcrunch.com"
    assert extract_root_domain("https://sub.venturebeat.com/ai") == "venturebeat.com"
    assert is_domain_independent("https://techcrunch.com/a", "https://venturebeat.com/b") is True
    assert is_domain_independent("https://techcrunch.com/a", "https://techcrunch.com/b") is False


def test_clean_html_to_text() -> None:
    html = """
    <html>
        <head><script>alert('bad');</script></head>
        <body>
            <nav><a href='/'>Home</a></nav>
            <h1>OpenAI Announces GPT-5</h1>
            <p>Today, OpenAI revealed their next flagship model with improved reasoning capabilities.</p>
            <footer>&copy; 2026 Tech News</footer>
        </body>
    </html>
    """
    cleaned = clean_html_to_text(html)
    assert "OpenAI Announces GPT-5" in cleaned
    assert "improved reasoning capabilities" in cleaned
    assert "alert" not in cleaned
    assert "Home" not in cleaned


def test_yesterday_cutoff() -> None:
    from app.services.ingestion.rss_fetcher import compute_yesterday_cutoff
    import zoneinfo
    from datetime import datetime, timedelta

    cutoff = compute_yesterday_cutoff("Asia/Phnom_Penh")
    tz = zoneinfo.ZoneInfo("Asia/Phnom_Penh")
    now_local = datetime.now(tz)
    expected_yesterday = now_local.date() - timedelta(days=1)
    cutoff_local = cutoff.astimezone(tz)
    assert cutoff_local.date() == expected_yesterday
    assert cutoff_local.hour == 0
    assert cutoff_local.minute == 0
    assert cutoff_local.second == 0


from unittest.mock import patch
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)


def test_article_repository_deduplication() -> None:
    with Session(test_engine) as session:
        repo = ArticleRepository(session)
        unique_url = f"https://example.com/test-{uuid.uuid4()}"
        art = Article(
            url=unique_url,
            title="Deduplication Test Article",
            content_hash=compute_article_hash(unique_url, "Deduplication Test Article"),
            status="pending",
        )
        saved, created = repo.create_if_not_exists(art)
        assert created is True

        # Duplicate insertion attempt
        dup = Article(
            url=unique_url,
            title="Deduplication Test Article",
            content_hash=compute_article_hash(unique_url, "Deduplication Test Article"),
            status="pending",
        )
        saved_dup, dup_created = repo.create_if_not_exists(dup)
        assert dup_created is False
        assert saved_dup.id == saved.id


@pytest.mark.asyncio
async def test_pipeline_with_mock_llm() -> None:
    with Session(test_engine) as session:
        # Pre-seed test articles
        art_repo = ArticleRepository(session)
        u1 = f"https://techcrunch.com/ai-{uuid.uuid4()}"
        u2 = f"https://venturebeat.com/ai-{uuid.uuid4()}"

        a1 = Article(
            url=u1,
            title="Breakthrough Reasoning Model Released",
            summary="New benchmark records achieved across mathematics and code.",
            content_hash=compute_article_hash(u1, "Breakthrough Reasoning Model Released"),
            status="pending",
        )
        a2 = Article(
            url=u2,
            title="Breakthrough Reasoning Model Released Independently",
            summary="Independent verification confirms benchmark records in reasoning.",
            content_hash=compute_article_hash(u2, "Breakthrough Reasoning Model Released Independently"),
            status="pending",
        )
        art_repo.create_if_not_exists(a1)
        art_repo.create_if_not_exists(a2)

        pipeline = IngestionPipeline(session, llm_provider=MockLLMProvider())
        # Avoid network calls to external RSS in unit test by mocking sources
        pipeline.source_repo.get_active_sources = lambda: []  # type: ignore[assignment]

        with patch("app.services.ingestion.pipeline.extract_article_text", return_value="Deep analysis of reasoning model performance and pricing."):
            result = await pipeline.run()

        assert result.candidates_screened > 0
        assert result.winning_article_id is not None
        assert result.winning_composite_score > 0.0


@pytest.mark.asyncio
async def test_pipeline_multi_client_dynamic_scoring_and_selection() -> None:
    """Verify that multi-client ingestion evaluates each client's industry criteria and elects unique winners per client."""
    from app.models.client import ClientProfile, ClientTopicFilter

    with Session(test_engine) as session:
        art_repo = ArticleRepository(session)
        score_repo = ArticleScoreRepository(session)

        # 1. Seed Client A (Logistics) and Client B (Healthcare)
        cl_a = ClientProfile(name="Apex Logistics AI", slug=f"apex-logistics-{uuid.uuid4().hex[:6]}", is_active=True)
        session.add(cl_a)
        session.commit()
        session.refresh(cl_a)
        tf_a = ClientTopicFilter(
            client_id=cl_a.id,
            industries='["logistics", "supply chain"]',
            focus_keywords='["freight", "warehouse automation"]',
            weight_economic=0.50,
            weight_actionability=0.30,
            weight_regulatory=0.10,
            weight_novelty=0.10,
        )
        session.add(tf_a)

        cl_b = ClientProfile(name="CureAI Health", slug=f"cureai-health-{uuid.uuid4().hex[:6]}", is_active=True)
        session.add(cl_b)
        session.commit()
        session.refresh(cl_b)
        tf_b = ClientTopicFilter(
            client_id=cl_b.id,
            industries='["healthcare", "medicine"]',
            focus_keywords='["clinical trials", "biotech"]',
            weight_regulatory=0.50,
            weight_actionability=0.30,
            weight_economic=0.10,
            weight_novelty=0.10,
        )
        session.add(tf_b)
        session.commit()

        # 2. Seed Article 1 (Logistics) and Article 2 (Healthcare)
        u_logistics = f"https://techcrunch.com/logistics-{uuid.uuid4()}"
        u_health = f"https://biotech.com/fda-ai-{uuid.uuid4()}"

        art_logistics = Article(
            url=u_logistics,
            title="Autonomous Freight and Warehouse Robotics Slashes Global Logistics Costs",
            summary="New supply chain automation breakthroughs achieve major cost reductions.",
            content_hash=compute_article_hash(u_logistics, "Autonomous Freight and Warehouse Robotics Slashes Global Logistics Costs"),
            status="pending",
        )
        art_health = Article(
            url=u_health,
            title="FDA Approves Breakthrough AI Diagnostic Platform for Oncology Clinical Trials",
            summary="New healthcare regulatory milestone speeds up biotech clinical drug discovery.",
            content_hash=compute_article_hash(u_health, "FDA Approves Breakthrough AI Diagnostic Platform for Oncology Clinical Trials"),
            status="pending",
        )
        art_logistics, _ = art_repo.create_if_not_exists(art_logistics)
        art_health, _ = art_repo.create_if_not_exists(art_health)

        # 3. Dynamic Mock LLM Provider that tailors scores based on profile_criteria
        class DynamicMultiClientMockLLM(MockLLMProvider):
            async def score_utility(
                self,
                title: str,
                full_text: str,
                profile_criteria: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                crit_text = str(profile_criteria or "").lower()
                title_lower = title.lower()

                if "logistics" in crit_text and "logistics" in title_lower:
                    return {
                        "composite_score": 0.95,
                        "actionability": 0.95,
                        "economic_impact": 0.95,
                        "regulatory_impact": 0.80,
                        "novelty": 0.90,
                        "reasoning": "Direct match for logistics supply chain client.",
                    }
                elif "healthcare" in crit_text and ("fda" in title_lower or "clinical" in title_lower):
                    return {
                        "composite_score": 0.96,
                        "actionability": 0.95,
                        "economic_impact": 0.80,
                        "regulatory_impact": 0.98,
                        "novelty": 0.95,
                        "reasoning": "Direct match for healthcare oncology client.",
                    }
                else:
                    return {
                        "composite_score": 0.45,
                        "actionability": 0.40,
                        "economic_impact": 0.40,
                        "regulatory_impact": 0.40,
                        "novelty": 0.50,
                        "reasoning": "Low relevance to client industry focus.",
                    }

        pipeline = IngestionPipeline(session, llm_provider=DynamicMultiClientMockLLM())
        pipeline.source_repo.get_active_sources = lambda: []  # type: ignore[assignment]

        with patch("app.services.ingestion.pipeline.extract_article_text", return_value="Detailed verification text."):
            result = await pipeline.run()

        # 4. Verify that each client dynamically got their own distinct winning article tailored to their industry!
        assert str(cl_a.id) in result.client_winners
        assert str(cl_b.id) in result.client_winners
        assert result.client_winners[str(cl_a.id)] == art_logistics.id
        assert result.client_winners[str(cl_b.id)] == art_health.id

        # Verify database records
        win_a = score_repo.get_winning_article(client_id=cl_a.id)
        win_b = score_repo.get_winning_article(client_id=cl_b.id)
        assert win_a is not None
        assert win_a.article_id == art_logistics.id
        assert win_b is not None
        assert win_b.article_id == art_health.id
        assert win_a.article_id != win_b.article_id


def test_news_api_endpoints(client: TestClient) -> None:
    # 1. Sources endpoint
    resp = client.get("/api/v1/news/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert isinstance(sources, list)
    assert len(sources) >= 5

    # 2. Articles endpoint
    resp_art = client.get("/api/v1/news/articles?limit=10")
    assert resp_art.status_code == 200
    articles = resp_art.json()
    assert isinstance(articles, list)

    # 3. Winner endpoint
    resp_win = client.get("/api/v1/news/articles/winner")
    assert resp_win.status_code == 200
    # Returns either winning ArticleDetailRead object or null

    # 4. Ingest status endpoint
    resp_status = client.get("/api/v1/news/ingest/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert "is_running" in status_data

    # 5. Background ingest trigger endpoint
    with patch("app.routes.news_routes.run_background_ingestion"):
        resp_ingest = client.post("/api/v1/news/ingest?background=true")
        assert resp_ingest.status_code == 200
        ingest_data = resp_ingest.json()
        assert ingest_data["status"] == "queued"


def test_story_clustering() -> None:
    from app.services.ingestion.verifier import cluster_candidates

    candidates = [
        {
            "id": "1",
            "title": "OpenAI announces new o3 reasoning model with major speedups",
            "url": "https://techcrunch.com/openai-o3",
        },
        {
            "id": "2",
            "title": "OpenAI unveils o3 reasoning model today",
            "url": "https://theverge.com/openai-o3-news",
        },
        {
            "id": "3",
            "title": "Google DeepMind unveils AlphaFold 3 breakthrough in biology",
            "url": "https://deepmind.google/alphafold3",
        },
    ]

    clusters = cluster_candidates(candidates)
    # The two OpenAI stories should be clustered together
    assert len(clusters) == 2
    lead_titles = [c["title"] for c in clusters]
    assert "OpenAI announces new o3 reasoning model with major speedups" in lead_titles
    assert "Google DeepMind unveils AlphaFold 3 breakthrough in biology" in lead_titles

    # Verify cluster secondaries
    openai_cluster = next(c for c in clusters if "o3" in c["title"])
    assert len(openai_cluster["cluster_secondaries"]) == 1
    assert openai_cluster["cluster_secondaries"][0]["url"] == "https://theverge.com/openai-o3-news"


@pytest.mark.asyncio
async def test_search_external_secondary_source_fallback() -> None:
    from app.services.ingestion.verifier import search_external_secondary_source

    mock_feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Google News</title>
        <item>
          <title>OpenAI Unveils Major Update - Reuters</title>
          <link>https://reuters.com/technology/openai-update</link>
          <description>Reuters report on OpenAI model.</description>
          <source url="https://reuters.com">Reuters</source>
        </item>
      </channel>
    </rss>
    """

    class MockResponse:
        status_code = 200
        text = mock_feed_xml

    with patch("httpx.AsyncClient.get", return_value=MockResponse()):
        res = await search_external_secondary_source(
            "OpenAI Unveils Major Update",
            "https://openai.com/blog/update"
        )
        assert res is not None
        assert "reuters.com" in res["url"]
        assert res["source_name"] == "Reuters"


@pytest.mark.asyncio
async def test_hybrid_filtering_and_minimum_quality_gate() -> None:
    """Verify that off-topic articles scoring below 0.60 are rejected by the quality gate."""
    from app.models.client import ClientProfile, ClientTopicFilter
    from app.repositories.client_repo import ClientProfileRepository

    with Session(engine) as session:
        client_repo = ClientProfileRepository(session)
        art_repo = ArticleRepository(session)
        score_repo = ArticleScoreRepository(session)

        # 1. Create Health Client
        cl_health = ClientProfile(name="Aetheria Health", slug=f"health-gate-{uuid.uuid4().hex[:6]}")
        session.add(cl_health)
        session.commit()
        session.refresh(cl_health)

        tf = ClientTopicFilter(
            client_id=cl_health.id,
            industries="Healthcare, Clinical Medicine",
            focus_keywords="clinical, diagnosis, hospital, doctor, patients, fda",
            excluded_keywords="crypto, gaming",
        )
        session.add(tf)
        session.commit()

        # 2. Add an off-topic tech commerce article
        art_url = f"https://techcrunch.com/agent-commerce-{uuid.uuid4().hex[:6]}"
        off_topic_art = Article(
            url=art_url,
            title="Meta teams up with Bret Taylor’s Sierra Technologies on new standards for AI agent commerce",
            summary="New conversational AI agent protocol for retail and customer transactions.",
            content_hash=compute_article_hash(art_url, "Meta teams up with Bret Taylor’s Sierra"),
            status="pending",
        )
        off_topic_art, _ = art_repo.create_if_not_exists(off_topic_art)

        # 3. Mock LLM that rates the off-topic article with low composite (0.35) for Health
        class LowRelevanceMockLLM(MockLLMProvider):
            async def score_utility(
                self,
                title: str,
                full_text: str,
                profile_criteria: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                return {
                    "composite_score": 0.35,
                    "actionability": 0.30,
                    "economic_impact": 0.30,
                    "regulatory_impact": 0.20,
                    "novelty": 0.50,
                    "client_relevance": 0.10,
                    "reasoning": "Off-topic consumer commerce story; zero application to clinical medicine.",
                }

        pipeline = IngestionPipeline(session, llm_provider=LowRelevanceMockLLM())
        pipeline.source_repo.get_active_sources = lambda: []  # type: ignore[assignment]

        try:
            with patch("app.services.ingestion.pipeline.extract_article_text", return_value="Detailed verification text."):
                result = await pipeline.run()

            # 4. Verify quality gate rejected electing a winner for Health Client!
            assert str(cl_health.id) not in result.client_winners
            win_rec = score_repo.get_winning_article(client_id=cl_health.id)
            assert win_rec is None
        finally:
            with Session(engine) as cleanup_session:
                from sqlmodel import delete
                cleanup_session.exec(delete(ArticleScore).where(ArticleScore.article_id == off_topic_art.id))
                cleanup_session.exec(delete(ArticleScore).where(ArticleScore.client_id == cl_health.id))
                cleanup_session.exec(delete(ArticleVerification).where(ArticleVerification.article_id == off_topic_art.id))
                cleanup_session.exec(delete(Article).where(Article.id == off_topic_art.id))
                cleanup_session.exec(delete(ClientTopicFilter).where(ClientTopicFilter.client_id == cl_health.id))
                cleanup_session.exec(delete(ClientProfile).where(ClientProfile.id == cl_health.id))
                cleanup_session.commit()


@pytest.mark.asyncio
async def test_fetch_rss_feed_html_detection_and_fallback() -> None:
    """Verify that fetch_rss_feed gracefully detects HTML pages and handles direct feedparser fallback."""
    from unittest.mock import MagicMock, patch
    from app.services.ingestion.rss_fetcher import fetch_rss_feed

    # 1. Test HTML webpage detection without RSS links
    mock_html_resp = MagicMock()
    mock_html_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_html_resp.text = "<!DOCTYPE html><html><head><title>News</title></head><body><h1>Not RSS</h1></body></html>"
    mock_html_resp.url = "https://example.gov.au/news"
    mock_html_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", return_value=mock_html_resp):
        items = await fetch_rss_feed("https://example.gov.au/news", only_yesterday_and_today=False)
        assert items == []

    # 2. Test valid XML RSS feed parsing
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Transport News</title>
        <item>
          <title>Heavy Vehicle Apprenticeship Expansion</title>
          <link>https://example.com/hv-apprenticeship</link>
          <description>New training incentives announced.</description>
        </item>
      </channel>
    </rss>"""
    mock_xml_resp = MagicMock()
    mock_xml_resp.headers = {"content-type": "application/rss+xml"}
    mock_xml_resp.text = mock_xml
    mock_xml_resp.url = "https://example.com/feed"
    mock_xml_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", return_value=mock_xml_resp):
        items = await fetch_rss_feed("https://example.com/feed", only_yesterday_and_today=False)
        assert len(items) == 1
        assert items[0]["title"] == "Heavy Vehicle Apprenticeship Expansion"
        assert items[0]["url"] == "https://example.com/hv-apprenticeship"


