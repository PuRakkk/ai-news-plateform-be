import uuid
from typing import Any
from sqlmodel import Session

from app.core.log import logger
from app.models.script import ScriptClaimAudit
from app.repositories.script_repo import (
    ScriptBeatRepository,
    ScriptClaimAuditRepository,
    ScriptRepository,
)
from app.schemas.script import (
    ScriptBeatRead,
    ScriptClaimAuditRead,
    ScriptDetailRead,
    ScriptGroundingSummary,
)
from app.services.llm.base import LLMProviderAdapter
from app.services.scripting.auditor import FactCheckingAuditorService
from app.services.scripting.scriptwriter import ScriptwriterService


class ScriptingPipeline:
    """Orchestrator for grounded 5-beat script generation and claim-level fact check auditing."""

    def __init__(
        self,
        session: Session,
        llm_provider: LLMProviderAdapter | None = None,
    ) -> None:
        self.session = session
        self.scriptwriter = ScriptwriterService(session, llm_provider)
        self.auditor = FactCheckingAuditorService(session, llm_provider)
        self.script_repo = ScriptRepository(session)
        self.beat_repo = ScriptBeatRepository(session)
        self.audit_repo = ScriptClaimAuditRepository(session)

    async def generate_and_audit(
        self,
        article_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        auto_audit: bool = True,
        enforce_grounding_revision: bool = True,
    ) -> ScriptDetailRead:
        """Run full end-to-end script generation, critique, revision, and persistence."""
        logger.info(f"Starting ScriptingPipeline for article_id={article_id}, client_id={client_id}")

        # 1. Generate Script and Beats
        script, beats = await self.scriptwriter.generate_script(
            article_id=article_id,
            client_id=client_id,
        )

        audits: list[ScriptClaimAudit] = []  # type: ignore[name-defined]
        summary_dict = {"total_claims": 0, "grounded_claims": 0, "grounding_ratio": 0.0, "is_fully_grounded": False}

        # 2. Run Claim-Level Fact-Checking Auditor
        if auto_audit:
            script, audits, summary_dict = await self.auditor.audit_script(
                script_id=script.id,
                auto_revise=enforce_grounding_revision,
            )
            # Reload beats in case revision updated them
            beats = self.beat_repo.get_by_script_id(script.id)

        # 3. Assemble DTO
        return ScriptDetailRead(
            id=script.id,
            article_id=script.article_id,
            client_id=script.client_id,
            title=script.title,
            persona_role=script.persona_role,
            total_estimated_duration_sec=script.total_estimated_duration_sec,
            call_to_action=script.call_to_action,
            status=script.status,
            created_at=script.created_at,
            beats=[ScriptBeatRead.model_validate(b) for b in beats],
            audits=[ScriptClaimAuditRead.model_validate(a) for a in audits],
            grounding_summary=ScriptGroundingSummary(**summary_dict),
        )

    def get_script_detail(self, script_id: uuid.UUID) -> ScriptDetailRead | None:
        """Retrieve script details including beats, audits, and grounding statistics."""
        script = self.script_repo.get_by_id(script_id)
        if not script:
            return None

        beats = self.beat_repo.get_by_script_id(script_id)
        audits = self.audit_repo.get_by_script_id(script_id)
        summary = self.audit_repo.get_grounded_summary(script_id)

        return ScriptDetailRead(
            id=script.id,
            article_id=script.article_id,
            client_id=script.client_id,
            title=script.title,
            persona_role=script.persona_role,
            total_estimated_duration_sec=script.total_estimated_duration_sec,
            call_to_action=script.call_to_action,
            status=script.status,
            created_at=script.created_at,
            beats=[ScriptBeatRead.model_validate(b) for b in beats],
            audits=[ScriptClaimAuditRead.model_validate(a) for a in audits],
            grounding_summary=ScriptGroundingSummary(**summary),
        )
