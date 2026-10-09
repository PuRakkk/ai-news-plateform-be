import uuid
from typing import Any
import pytest
from starlette.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)
from app.models.client import ClientPersona, ClientProfile, ClientTopicFilter
from app.models.news import Article
from app.models.script import Script, ScriptBeat, ScriptClaimAudit
from app.repositories.client_repo import (
    ClientPersonaRepository,
    ClientProfileRepository,
    ClientTopicFilterRepository,
)
from app.repositories.news_repo import ArticleRepository
from app.repositories.script_repo import (
    ScriptBeatRepository,
    ScriptClaimAuditRepository,
    ScriptRepository,
)
from app.schemas.client import (
    ClientPersonaCreate,
    ClientPersonaUpdate,
    ClientProfileCreate,
    ClientTopicFilterCreate,
    ClientTopicFilterUpdate,
)
from app.services.client_service import ClientService
from app.services.llm.base import LLMProviderAdapter
from app.services.scripting.auditor import FactCheckingAuditorService
from app.services.scripting.pipeline import ScriptingPipeline
from app.services.scripting.scriptwriter import ScriptwriterService


class MockScriptingLLMProvider(LLMProviderAdapter):
    """Mock LLM adapter for deterministic testing of Phase 2 scriptwriting and fact-checking."""

    def __init__(self, simulate_hallucination: bool = False) -> None:
        self.simulate_hallucination = simulate_hallucination
        self.revision_called = False

    async def screen_candidates(
        self,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
        topic_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def verify_corroboration(
        self,
        primary_title: str,
        primary_text: str,
        secondary_title: str,
        secondary_text: str,
    ) -> dict[str, Any]:
        return {"agreement_score": 0.9, "is_verified": True, "corroboration_notes": "Corroborated."}

    async def score_utility(
        self,
        title: str,
        full_text: str,
        profile_criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"composite_score": 0.85, "actionability": 0.9, "economic_impact": 0.8, "regulatory_impact": 0.7, "novelty": 0.9, "reasoning": "High utility"}

    async def generate_script(
        self,
        article_title: str,
        full_text: str,
        persona: dict[str, Any],
        topic_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role = persona.get("persona_role", "AI Chief of Staff")
        cta = persona.get("default_cta", "Follow for daily executive AI updates.")
        return {
            "title": f"Executive Briefing: {article_title}",
            "persona_role": role,
            "total_estimated_duration_sec": 75,
            "call_to_action": cta,
            "beats": [
                {
                    "beat_index": 1,
                    "beat_type": "HOOK",
                    "spoken_script": f"If you deploy AI systems, you need to understand this breakthrough: {article_title}.",
                    "visual_directive": "PRESENTER_CAMERA_A",
                    "whiteboard_directive": "Headline badge with metric",
                    "estimated_seconds": 10,
                },
                {
                    "beat_index": 2,
                    "beat_type": "CONTEXT",
                    "spoken_script": "Until today, high latency in foundation models caused enterprise workflows to stall.",
                    "visual_directive": "PRESENTER_CAMERA_A",
                    "whiteboard_directive": "Legacy latency flowchart",
                    "estimated_seconds": 15,
                },
                {
                    "beat_index": 3,
                    "beat_type": "CORE_SHIFT",
                    "spoken_script": "Researchers have slashed token communication overhead by 68% using a deterministic protocol.",
                    "visual_directive": "PRESENTER_CAMERA_B_SPLIT",
                    "whiteboard_directive": "68% latency reduction chart",
                    "estimated_seconds": 25,
                },
                {
                    "beat_index": 4,
                    "beat_type": "BUSINESS_IMPACT",
                    "spoken_script": "This directly drops compute costs per user query by nearly half, protecting operating margins.",
                    "visual_directive": "PRESENTER_CAMERA_A_PUNCH_IN",
                    "whiteboard_directive": "Unit economics margin shift",
                    "estimated_seconds": 15,
                },
                {
                    "beat_index": 5,
                    "beat_type": "CTA",
                    "spoken_script": f"Audit your internal inference pipeline this week. {cta}",
                    "visual_directive": "PRESENTER_CAMERA_A",
                    "whiteboard_directive": None,
                    "estimated_seconds": 10,
                },
            ],
        }

    async def audit_claims(
        self,
        beats: list[dict[str, Any]],
        full_text: str,
    ) -> list[dict[str, Any]]:
        # If simulating hallucination and revision hasn't occurred yet
        if self.simulate_hallucination and not self.revision_called:
            return [
                {
                    "beat_index": 1,
                    "claim_text": "AI breakthrough announcement",
                    "verified_citation": "Section 1",
                    "source_verbatim_quote": "A new breakthrough was announced.",
                    "is_grounded": True,
                    "audit_notes": "Verified in introduction.",
                },
                {
                    "beat_index": 3,
                    "claim_text": "Researchers achieved 99% accuracy on impossible benchmark",
                    "verified_citation": None,
                    "source_verbatim_quote": None,
                    "is_grounded": False,
                    "audit_notes": "Not supported by source article text.",
                },
            ]

        # Normal fully grounded audit
        return [
            {
                "beat_index": 1,
                "claim_text": "Foundation model breakthrough",
                "verified_citation": "Paragraph 1",
                "source_verbatim_quote": "Researchers announced a new architecture.",
                "is_grounded": True,
                "audit_notes": "Verbatim quote matches lead paragraph.",
            },
            {
                "beat_index": 3,
                "claim_text": "Latency reduced by 68%",
                "verified_citation": "Paragraph 3",
                "source_verbatim_quote": "slashed communication latency by 68%",
                "is_grounded": True,
                "audit_notes": "Exact percentage and protocol verified.",
            },
            {
                "beat_index": 4,
                "claim_text": "Drop in compute cost per query",
                "verified_citation": "Paragraph 4",
                "source_verbatim_quote": "halving inference infrastructure cost",
                "is_grounded": True,
                "audit_notes": "Economic impact corroborated.",
            },
        ]

    async def revise_script_beat(
        self,
        beat: dict[str, Any],
        ungrounded_claims: list[dict[str, Any]],
        full_text: str,
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        self.revision_called = True
        return {
            "spoken_script": "Researchers have verified a 68% communication latency reduction using standard benchmarks.",
            "visual_directive": "PRESENTER_CAMERA_B_SPLIT",
            "whiteboard_directive": "Verified 68% reduction",
            "estimated_seconds": 25,
            "revision_notes": "Removed unsupported claim and replaced with verified 68% latency reduction.",
        }


# ==============================================================================
# 1. CLIENT PROFILE & PERSONA TESTS
# ==============================================================================

def test_client_profile_and_persona_creation() -> None:
    with Session(test_engine) as session:
        client_repo = ClientProfileRepository(session)
        persona_repo = ClientPersonaRepository(session)
        topic_repo = ClientTopicFilterRepository(session)

        uid_suffix = uuid.uuid4().hex[:6]
        client = client_repo.create_client(
            name=f"Test Logistics AI {uid_suffix}",
            slug=f"test-logistics-{uid_suffix}",
        )
        assert client.id is not None
        assert client.is_active is True

        persona = persona_repo.upsert_persona(
            client_id=client.id,
            persona_role="Supply Chain AI Specialist",
            tone_of_voice="Pragmatic, metrics-driven",
            target_audience="Logistics Directors & COOs",
            default_cta="Subscribe to our Weekly Freight AI dispatch.",
        )
        assert persona.persona_role == "Supply Chain AI Specialist"

        topic_filter = topic_repo.upsert_topic_filter(
            client_id=client.id,
            industries=["logistics", "supply chain"],
            focus_keywords=["autonomous fleet", "warehouse robotics"],
            excluded_keywords=["gaming", "crypto"],
            weight_actionability=0.50,
            weight_economic=0.30,
            weight_regulatory=0.10,
            weight_novelty=0.10,
        )
        assert "logistics" in topic_filter.industries
        assert topic_filter.weight_actionability == 0.50

        # Verify bundle retrieval
        p, per, top = client_repo.get_client_bundle(client.id)
        assert p is not None
        assert per is not None and per.persona_role == "Supply Chain AI Specialist"
        assert top is not None and "warehouse robotics" in top.focus_keywords


def test_client_service_management() -> None:
    with Session(test_engine) as session:
        service = ClientService(session)
        uid_suffix = uuid.uuid4().hex[:6]

        created = service.create_client(
            ClientProfileCreate(
                name=f"Healthcare AI {uid_suffix}",
                slug=f"healthcare-ai-{uid_suffix}",
                persona=ClientPersonaCreate(
                    persona_role="Clinical AI Director",
                    tone_of_voice="Scientific, rigorous, calm",
                    target_audience="Chief Medical Officers and Hospital Administrators",
                    default_cta="Download the Clinical AI Adoption Whitepaper.",
                ),
                topic_filter=ClientTopicFilterCreate(
                    industries='["healthcare", "biotech"]',
                    focus_keywords='["fda approval", "diagnostics"]',
                    excluded_keywords='["consumer apps"]',
                ),
            )
        )
        assert created.slug == f"healthcare-ai-{uid_suffix}"
        assert created.persona is not None
        assert created.persona.persona_role == "Clinical AI Director"

        # Update persona
        updated_persona = service.update_persona(
            created.id,
            ClientPersonaUpdate(persona_role="Chief Medical AI Officer"),
        )
        assert updated_persona is not None
        assert updated_persona.persona_role == "Chief Medical AI Officer"
        assert updated_persona.tone_of_voice == "Scientific, rigorous, calm"


# ==============================================================================
# 2. SCRIPT & AUDIT REPOSITORY TESTS
# ==============================================================================

def test_script_and_audit_repositories() -> None:
    with Session(test_engine) as session:
        article_repo = ArticleRepository(session)
        script_repo = ScriptRepository(session)
        beat_repo = ScriptBeatRepository(session)
        audit_repo = ScriptClaimAuditRepository(session)

        # Create dummy article
        uid_suffix = uuid.uuid4().hex[:6]
        article = Article(
            url=f"https://example.com/script-test-{uid_suffix}",
            title=f"New Agent Architecture {uid_suffix}",
            summary="Breakthrough in multi-agent routing.",
            full_text="Researchers have slashed communication latency by 68% halving inference infrastructure cost.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        article_repo.create_if_not_exists(article)

        # Create script
        script = script_repo.create_script(
            article_id=article.id,
            client_id=None,
            title="Slashed Agent Latency",
            persona_role="AI Chief of Staff",
            total_estimated_duration_sec=75,
            call_to_action="Follow for updates.",
            status="draft",
        )
        assert script.status == "draft"

        # Insert 5 beats
        beats = [
            ScriptBeat(
                script_id=script.id,
                beat_index=i,
                beat_type=["HOOK", "CONTEXT", "CORE_SHIFT", "BUSINESS_IMPACT", "CTA"][i - 1],
                spoken_script=f"Spoken text for beat {i}",
                visual_directive="PRESENTER_CAMERA_A",
                estimated_seconds=15,
            )
            for i in range(1, 6)
        ]
        saved_beats = beat_repo.replace_beats_for_script(script.id, beats)
        assert len(saved_beats) == 5

        # Insert audits
        audits = [
            ScriptClaimAudit(
                script_id=script.id,
                beat_index=3,
                claim_text="Latency slashed by 68%",
                verified_citation="Section 1",
                source_verbatim_quote="slashed communication latency by 68%",
                is_grounded=True,
                audit_notes="Grounded in text",
            ),
            ScriptClaimAudit(
                script_id=script.id,
                beat_index=4,
                claim_text="Compute costs cut in half",
                verified_citation="Section 2",
                source_verbatim_quote="halving inference infrastructure cost",
                is_grounded=True,
                audit_notes="Corroborated",
            ),
        ]
        saved_audits = audit_repo.replace_audits_for_script(script.id, audits)
        assert len(saved_audits) == 2

        summary = audit_repo.get_grounded_summary(script.id)
        assert summary["total_claims"] == 2
        assert summary["grounded_claims"] == 2
        assert summary["is_fully_grounded"] is True


# ==============================================================================
# 3. SCRIPTWRITER & AUDITOR SERVICE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_scriptwriter_service() -> None:
    with Session(test_engine) as session:
        article_repo = ArticleRepository(session)
        uid_suffix = uuid.uuid4().hex[:6]
        article = Article(
            url=f"https://example.com/test-scriptwriter-{uid_suffix}",
            title="MIT Releases Multi-Agent Optimization Framework",
            summary="A breakthrough in distributed agent communications.",
            full_text="Researchers slashed communication latency by 68% halving inference infrastructure cost.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        article_repo.create_if_not_exists(article)

        mock_llm = MockScriptingLLMProvider()
        writer = ScriptwriterService(session, llm_provider=mock_llm)

        script, beats = await writer.generate_script(article.id)
        assert script.title.startswith("Executive Briefing:")
        assert len(beats) == 5
        assert [b.beat_type for b in beats] == ["HOOK", "CONTEXT", "CORE_SHIFT", "BUSINESS_IMPACT", "CTA"]
        assert script.total_estimated_duration_sec >= 60


@pytest.mark.asyncio
async def test_fact_checking_auditor_and_revision_loop() -> None:
    with Session(test_engine) as session:
        article_repo = ArticleRepository(session)
        uid_suffix = uuid.uuid4().hex[:6]
        article = Article(
            url=f"https://example.com/test-auditor-{uid_suffix}",
            title="Deterministic Agent Protocols",
            summary="Deterministic routing for AI agents.",
            full_text="A new breakthrough was announced. Researchers slashed communication latency by 68%.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        article_repo.create_if_not_exists(article)

        # Simulate hallucinated claim triggering critic revision loop
        mock_llm = MockScriptingLLMProvider(simulate_hallucination=True)
        writer = ScriptwriterService(session, llm_provider=mock_llm)
        auditor = FactCheckingAuditorService(session, llm_provider=mock_llm)

        script, _ = await writer.generate_script(article.id)
        assert script.status == "draft"

        # Audit script with auto_revise=True
        audited_script, audits, summary = await auditor.audit_script(script.id, auto_revise=True)

        assert mock_llm.revision_called is True
        assert audited_script.status == "audited"
        assert summary["is_fully_grounded"] is True


@pytest.mark.asyncio
async def test_scripting_pipeline_end_to_end() -> None:
    with Session(test_engine) as session:
        article_repo = ArticleRepository(session)
        client_repo = ClientProfileRepository(session)
        persona_repo = ClientPersonaRepository(session)

        uid_suffix = uuid.uuid4().hex[:6]
        client = client_repo.create_client(f"Enterprise AI {uid_suffix}", f"ent-ai-{uid_suffix}")
        persona_repo.upsert_persona(
            client_id=client.id,
            persona_role="Enterprise CTO",
            default_cta="Book a strategy call with our AI practice.",
        )

        article = Article(
            url=f"https://example.com/test-pipeline-{uid_suffix}",
            title="Foundation Model Scaling Laws Revisited",
            summary="Efficiency improvements change GPU deployment economics.",
            full_text="Researchers slashed communication latency by 68% halving inference infrastructure cost.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        article_repo.create_if_not_exists(article)

        mock_llm = MockScriptingLLMProvider()
        pipeline = ScriptingPipeline(session, llm_provider=mock_llm)

        result = await pipeline.generate_and_audit(
            article_id=article.id,
            client_id=client.id,
            auto_audit=True,
            enforce_grounding_revision=True,
        )

        assert result.title.startswith("Executive Briefing:")
        assert result.persona_role == "Enterprise CTO"
        assert len(result.beats) == 5
        assert result.call_to_action == "Book a strategy call with our AI practice."
        assert result.status == "audited"
        assert result.grounding_summary is not None
        assert result.grounding_summary.is_fully_grounded is True


# ==============================================================================
# 4. API ROUTE INTEGRATION TESTS
# ==============================================================================

def test_api_client_and_script_routes(client: TestClient) -> None:
    uid_suffix = uuid.uuid4().hex[:6]

    # 1. Create client profile via API
    create_resp = client.post(
        "/api/v1/clients/",
        json={
            "name": f"Robotics Corp {uid_suffix}",
            "slug": f"robotics-corp-{uid_suffix}",
            "is_active": True,
            "persona": {
                "persona_role": "Robotics VP",
                "tone_of_voice": "Direct, technical",
                "target_audience": "Hardware and automation engineers",
                "default_cta": "Follow for daily robotics insights.",
            },
            "topic_filter": {
                "industries": '["robotics"]',
                "focus_keywords": '["actuators", "locomotion"]',
                "excluded_keywords": '["finance"]',
            },
        },
    )
    assert create_resp.status_code == 201
    client_data = create_resp.json()
    client_id = client_data["id"]
    assert client_data["slug"] == f"robotics-corp-{uid_suffix}"
    assert client_data["persona"]["persona_role"] == "Robotics VP"

    # 2. Get client detail
    get_resp = client.get(f"/api/v1/clients/{client_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == f"Robotics Corp {uid_suffix}"

    # 3. Update persona
    put_resp = client.put(
        f"/api/v1/clients/{client_id}/persona",
        json={"persona_role": "Chief Robotics Officer"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["persona_role"] == "Chief Robotics Officer"

    # 4. Create an article in the DB for script generation test
    with Session(engine) as session:
        art_repo = ArticleRepository(session)
        article = Article(
            url=f"https://example.com/api-test-{uid_suffix}",
            title=f"Robot Learning Breakthrough {uid_suffix}",
            summary="New imitation learning benchmark reached.",
            full_text="Researchers slashed communication latency by 68% in humanoid robot fleet coordination.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        art_repo.create_if_not_exists(article)
        article_id = str(article.id)

    # 5. Generate script via API
    from unittest.mock import patch
    with patch("app.services.scripting.scriptwriter.get_llm_provider", return_value=MockScriptingLLMProvider()):
        gen_resp = client.post(
            "/api/v1/scripts/generate",
            json={
                "article_id": article_id,
                "client_id": client_id,
                "auto_audit": False,
            },
        )
    assert gen_resp.status_code == 201
    gen_data = gen_resp.json()
    script_id = gen_data["script"]["id"]
    assert len(gen_data["script"]["beats"]) == 5
    assert gen_data["script"]["persona_role"] == "Chief Robotics Officer"

    # 6. Retrieve script detail via API
    script_resp = client.get(f"/api/v1/scripts/{script_id}")
    assert script_resp.status_code == 200
    assert script_resp.json()["id"] == script_id

    # 7. List scripts via API
    list_resp = client.get(f"/api/v1/scripts/?client_id={client_id}")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 8. Clean up created client, script, and article in child-to-parent order
    with Session(engine) as cleanup_session:
        from sqlmodel import delete
        from app.models.client import ClientBrandKit, ClientPersona, ClientProfile, ClientTopicFilter
        c_uuid = uuid.UUID(client_id)
        a_uuid = uuid.UUID(article_id)
        s_uuid = uuid.UUID(script_id)
        cleanup_session.exec(delete(ScriptBeat).where(ScriptBeat.script_id == s_uuid))
        cleanup_session.exec(delete(Script).where(Script.id == s_uuid))
        cleanup_session.exec(delete(ClientTopicFilter).where(ClientTopicFilter.client_id == c_uuid))
        cleanup_session.exec(delete(ClientPersona).where(ClientPersona.client_id == c_uuid))
        cleanup_session.exec(delete(ClientBrandKit).where(ClientBrandKit.client_id == c_uuid))
        cleanup_session.exec(delete(ClientProfile).where(ClientProfile.id == c_uuid))
        cleanup_session.exec(delete(Article).where(Article.id == a_uuid))
        cleanup_session.commit()


def test_get_scriptwriting_prompt_client_tailored() -> None:
    """Verify that get_scriptwriting_prompt properly tailors system and user prompts to client profile and persona."""
    from app.services.llm.prompts import get_scriptwriting_prompt

    persona = {
        "client_name": "Major Training Group",
        "persona_role": "Crystal // Vocational Training & Apprenticeship Lead",
        "tone_of_voice": "Warm, encouraging, plain English, authoritative, grounded Australian trade voice",
        "target_audience": "Australian apprentices, trainees, and employers in transport and civil construction",
        "default_cta": "Visit major.edu.au to get started.",
    }
    topic_filter = {
        "industries": '["vocational_education_training", "transport_heavy_vehicle"]',
        "focus_keywords": '["Certificate III in Driving Operations", "apprenticeships"]',
    }

    system_prompt, user_prompt = get_scriptwriting_prompt(
        article_title="Major Training & Kinetic Traineeship Expansion",
        full_text="Major Training Group partners with Kinetic to expand bus driver traineeships.",
        persona=persona,
        topic_filter=topic_filter,
    )

    # 1. System prompt is client-specific and mentions avatar delivery
    assert "Major Training Group" in system_prompt
    assert "digital video avatar" in system_prompt

    # 2. User prompt contains client organization and persona identity
    assert "Client Organization: Major Training Group" in user_prompt
    assert "Crystal // Vocational Training & Apprenticeship Lead" in user_prompt
    assert "grounded Australian trade voice" in user_prompt
    assert "Visit major.edu.au" in user_prompt
    assert "vocational_education_training" in user_prompt

    # 3. User prompt contains teleprompter and 5-beat progressive structure
    assert "Beat 1 (HOOK" in user_prompt
    assert "Beat 2 (CONTEXT" in user_prompt
    assert "Beat 3 (CORE_SHIFT" in user_prompt
    assert "Beat 4 (BUSINESS_IMPACT" in user_prompt
    assert "Beat 5 (CTA" in user_prompt
    assert "HeyGen avatar" in user_prompt

