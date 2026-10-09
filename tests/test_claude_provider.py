import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.config import Settings
from app.services.llm.claude_provider import ClaudeProvider, _extract_json
from app.services.llm.factory import get_llm_provider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider


class DummyBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.content = [DummyBlock(text)]


def test_extract_json_variants() -> None:
    # 1. Plain JSON string
    raw = '{"name": "test", "val": 123}'
    assert _extract_json(raw) == {"name": "test", "val": 123}

    # 2. Markdown fenced JSON
    fenced = '```json\n{"status": "ok"}\n```'
    assert _extract_json(fenced) == {"status": "ok"}

    # 3. Generic markdown fence
    generic_fenced = '```\n{"status": "ok"}\n```'
    assert _extract_json(generic_fenced) == {"status": "ok"}

    # 4. Text around JSON object
    wrapped = 'Here is the requested output:\n{"screened": []}\nHope that helps!'
    assert _extract_json(wrapped) == {"screened": []}

    # 5. Text around JSON list
    wrapped_list = 'Output:\n[{"id": 1}]\nDone'
    assert _extract_json(wrapped_list) == [{"id": 1}]


def test_claude_provider_initialization() -> None:
    provider = ClaudeProvider(api_key="test-api-key", model="claude-3-5-haiku-20241022")
    assert provider.api_key == "test-api-key"
    assert provider.model == "claude-3-5-haiku-20241022"


@pytest.mark.asyncio
async def test_screen_candidates_success() -> None:
    provider = ClaudeProvider(api_key="test-key")
    mock_response = DummyResponse(
        json.dumps(
            {
                "screened": [
                    {"article_id": "art-1", "title": "Article 1", "url": "https://a.com", "relevance_score": 0.95},
                    {"article_id": "art-2", "title": "Article 2", "url": "https://b.com", "relevance_score": 0.85},
                ]
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        candidates = [
            {"id": "art-1", "title": "Article 1", "url": "https://a.com"},
            {"id": "art-2", "title": "Article 2", "url": "https://b.com"},
        ]
        result = await provider.screen_candidates(candidates, top_k=2)

        assert len(result) == 2
        assert result[0]["article_id"] == "art-1"
        assert result[0]["relevance_score"] == 0.95
        mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_screen_candidates_fallback_on_error() -> None:
    provider = ClaudeProvider(api_key="test-key")

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = RuntimeError("API connection failure")

        candidates = [{"id": "c1", "title": "Title 1", "url": "https://c1.com"}]
        result = await provider.screen_candidates(candidates, top_k=1)

        assert len(result) == 1
        assert result[0]["article_id"] == "c1"
        assert result[0]["relevance_score"] == 0.5
        assert "Fallback screening" in result[0]["screening_reason"]


@pytest.mark.asyncio
async def test_verify_corroboration_success() -> None:
    provider = ClaudeProvider(api_key="test-key")
    mock_response = DummyResponse(
        json.dumps(
            {
                "agreement_score": 0.88,
                "is_verified": True,
                "corroboration_notes": "Both sources confirm the release.",
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        res = await provider.verify_corroboration(
            primary_title="Headline 1",
            primary_text="Primary text body",
            secondary_title="Headline 2",
            secondary_text="Secondary text body",
        )

        assert res["agreement_score"] == 0.88
        assert res["is_verified"] is True
        assert "confirm" in res["corroboration_notes"]


@pytest.mark.asyncio
async def test_verify_corroboration_fallback_on_error() -> None:
    provider = ClaudeProvider(api_key="test-key")

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = RuntimeError("Claude rate limit")

        res = await provider.verify_corroboration(
            primary_title="Headline 1",
            primary_text="Text 1",
            secondary_title="Headline 2",
            secondary_text="Text 2",
        )

        assert res["agreement_score"] == 0.0
        assert res["is_verified"] is False
        assert "Verification error" in res["corroboration_notes"]


@pytest.mark.asyncio
async def test_score_utility_success() -> None:
    provider = ClaudeProvider(api_key="test-key")
    mock_response = DummyResponse(
        json.dumps(
            {
                "actionability": 0.9,
                "economic_impact": 0.8,
                "regulatory_impact": 0.4,
                "novelty": 0.7,
                "client_relevance": 1.0,
                "reasoning": "High impact enterprise workflow breakthrough.",
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        res = await provider.score_utility(
            title="AI Revolution in Logistics",
            full_text="Article details regarding enterprise robotics...",
            profile_criteria={"weights": {"actionability": 0.5, "economic_impact": 0.5, "regulatory_impact": 0.0, "novelty": 0.0}},
        )

        # Expected base_composite = 0.5 * 0.9 + 0.5 * 0.8 = 0.85
        assert res["composite_score"] == 0.85
        assert res["actionability"] == 0.9
        assert res["economic_impact"] == 0.8


@pytest.mark.asyncio
async def test_generate_script_success() -> None:
    provider = ClaudeProvider(api_key="test-key")
    mock_response = DummyResponse(
        json.dumps(
            {
                "title": "Autonomous Drone Fleet Launch",
                "persona_role": "AI Chief of Staff",
                "total_estimated_duration_sec": 75,
                "call_to_action": "Subscribe for daily AI briefings.",
                "beats": [
                    {
                        "beat_index": 1,
                        "beat_type": "HOOK",
                        "spoken_script": "Drones are transforming warehouse logistics today.",
                        "visual_directive": "PRESENTER_CAMERA_A",
                        "whiteboard_directive": "Graphic 1",
                        "estimated_seconds": 12,
                    }
                ],
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        persona = {"persona_role": "AI Chief of Staff", "default_cta": "Subscribe for daily AI briefings."}
        res = await provider.generate_script(
            article_title="Drone Fleet Launch",
            full_text="Warehouse automation news...",
            persona=persona,
        )

        assert res["title"] == "Autonomous Drone Fleet Launch"
        assert len(res["beats"]) == 1
        assert res["beats"][0]["beat_type"] == "HOOK"


@pytest.mark.asyncio
async def test_audit_claims_and_revise_beat() -> None:
    provider = ClaudeProvider(api_key="test-key")

    # 1. Audit claims
    audit_response = DummyResponse(
        json.dumps(
            {
                "claims": [
                    {
                        "beat_index": 1,
                        "claim_text": "Fleet reduced costs by 40%",
                        "verified_citation": "Paragraph 2",
                        "source_verbatim_quote": "cutting operating expenditures by 40%",
                        "is_grounded": True,
                        "audit_notes": "Direct quote found in text",
                    }
                ]
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = audit_response

        claims = await provider.audit_claims(
            beats=[{"beat_index": 1, "spoken_script": "Fleet reduced costs by 40%"}],
            full_text="Company reported cutting operating expenditures by 40% in Q3.",
        )

        assert len(claims) == 1
        assert claims[0]["is_grounded"] is True
        assert claims[0]["beat_index"] == 1

    # 2. Revise beat
    revise_response = DummyResponse(
        json.dumps(
            {
                "spoken_script": "Rewritten grounded text backed by facts.",
                "visual_directive": "PRESENTER_CAMERA_A",
                "whiteboard_directive": None,
                "estimated_seconds": 15,
                "revision_notes": "Corrected assertion",
            }
        )
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = revise_response

        revised = await provider.revise_script_beat(
            beat={"beat_index": 1, "spoken_script": "Speculative text"},
            ungrounded_claims=[{"claim_text": "Unverified claim"}],
            full_text="Verified facts...",
            persona={"persona_role": "AI Chief of Staff"},
        )

        assert revised["spoken_script"] == "Rewritten grounded text backed by facts."
        assert revised["revision_notes"] == "Corrected assertion"


def test_factory_get_llm_provider() -> None:
    with patch("app.services.llm.factory.settings.LLM_PROVIDER", "claude"):
        provider = get_llm_provider()
        assert isinstance(provider, ClaudeProvider)

    with patch("app.services.llm.factory.settings.LLM_PROVIDER", "anthropic"):
        provider = get_llm_provider()
        assert isinstance(provider, ClaudeProvider)

    with patch("app.services.llm.factory.settings.LLM_PROVIDER", "gemini"):
        provider = get_llm_provider()
        assert isinstance(provider, GeminiProvider)

    with patch("app.services.llm.factory.settings.LLM_PROVIDER", "openai"):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)


def test_settings_validation_for_claude() -> None:
    # Production without Claude key should fail
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY or CLAUDE_API_KEY must be configured"):
        Settings(
            APP_ENV="production",
            JWT_SECRET="long_secure_random_jwt_secret_value_12345",
            SECRET_ENCRYPTION_KEY="k" * 32,
            LLM_PROVIDER="claude",
            ANTHROPIC_API_KEY="",
            CLAUDE_API_KEY=None,
        )

    # Production with Claude key should succeed
    s = Settings(
        APP_ENV="production",
        JWT_SECRET="long_secure_random_jwt_secret_value_12345",
        SECRET_ENCRYPTION_KEY="k" * 32,
        LLM_PROVIDER="claude",
        ANTHROPIC_API_KEY="sk-ant-test-secret-key-12345",
    )
    assert s.effective_claude_api_key == "sk-ant-test-secret-key-12345"
