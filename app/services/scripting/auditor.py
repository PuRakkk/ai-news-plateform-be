import uuid
from typing import Any
from sqlmodel import Session

from app.core.config import settings
from app.core.log import logger
from app.models.script import Script, ScriptBeat, ScriptClaimAudit
from app.repositories.client_repo import ClientPersonaRepository
from app.repositories.news_repo import ArticleRepository
from app.repositories.script_repo import (
    ScriptBeatRepository,
    ScriptClaimAuditRepository,
    ScriptRepository,
)
from app.services.llm.base import LLMProviderAdapter
from app.services.llm.factory import get_llm_provider


class FactCheckingAuditorService:
    """Claim-Level Fact-Checking Auditor with automated critique and revision loop."""

    def __init__(
        self,
        session: Session,
        llm_provider: LLMProviderAdapter | None = None,
    ) -> None:
        self.session = session
        self.llm_provider = llm_provider or get_llm_provider()
        self.article_repo = ArticleRepository(session)
        self.script_repo = ScriptRepository(session)
        self.beat_repo = ScriptBeatRepository(session)
        self.audit_repo = ScriptClaimAuditRepository(session)
        self.persona_repo = ClientPersonaRepository(session)

    async def audit_script(
        self,
        script_id: uuid.UUID,
        auto_revise: bool = True,
    ) -> tuple[Script, list[ScriptClaimAudit], dict[str, Any]]:
        """Extract atomic assertions, verify against source verbatim quotes, and auto-correct ungrounded beats."""
        script = self.script_repo.get_by_id(script_id)
        if not script:
            raise ValueError(f"Script with id {script_id} not found.")

        article = self.article_repo.get_by_id(script.article_id)
        if not article:
            raise ValueError(f"Referenced article {script.article_id} not found.")

        beats = self.beat_repo.get_by_script_id(script_id)
        if not beats:
            raise ValueError(f"Script {script_id} has no beats to audit.")

        article_text = article.full_text or article.summary or article.title

        beats_payload = [
            {
                "beat_index": b.beat_index,
                "beat_type": b.beat_type,
                "spoken_script": b.spoken_script,
                "visual_directive": b.visual_directive,
                "whiteboard_directive": b.whiteboard_directive,
                "estimated_seconds": b.estimated_seconds,
            }
            for b in beats
        ]

        logger.info(f"Auditing factual claims for script id={script_id}...")
        raw_claims = await self.llm_provider.audit_claims(beats_payload, article_text)

        # Check for ungrounded claims
        ungrounded = [c for c in raw_claims if not c.get("is_grounded", False)]

        # Critique / Revision Loop: if ungrounded claims exist and auto_revise is True
        if ungrounded and auto_revise:
            logger.warning(
                f"Found {len(ungrounded)} ungrounded claim(s) in script {script_id}. Triggering revision loop..."
            )
            persona_data = {"persona_role": script.persona_role}
            if script.client_id:
                persona_record = self.persona_repo.get_by_client_id(script.client_id)
                if persona_record:
                    persona_data.update(
                        {
                            "persona_role": persona_record.persona_role,
                            "tone_of_voice": persona_record.tone_of_voice,
                            "target_audience": persona_record.target_audience,
                            "default_cta": persona_record.default_cta,
                        }
                    )

            # Group ungrounded claims by beat index
            by_beat: dict[int, list[dict[str, Any]]] = {}
            for u in ungrounded:
                idx = int(u.get("beat_index", 1))
                by_beat.setdefault(idx, []).append(u)

            # Revise each affected beat
            updated = False
            for beat in beats:
                if beat.beat_index in by_beat:
                    beat_dict = {
                        "beat_index": beat.beat_index,
                        "beat_type": beat.beat_type,
                        "spoken_script": beat.spoken_script,
                        "visual_directive": beat.visual_directive,
                        "whiteboard_directive": beat.whiteboard_directive,
                        "estimated_seconds": beat.estimated_seconds,
                    }
                    revised = await self.llm_provider.revise_script_beat(
                        beat=beat_dict,
                        ungrounded_claims=by_beat[beat.beat_index],
                        full_text=article_text,
                        persona=persona_data,
                    )
                    beat.spoken_script = revised.get("spoken_script", beat.spoken_script)
                    beat.visual_directive = revised.get("visual_directive", beat.visual_directive)
                    beat.whiteboard_directive = revised.get("whiteboard_directive", beat.whiteboard_directive)
                    beat.estimated_seconds = int(revised.get("estimated_seconds", beat.estimated_seconds))
                    updated = True

            if updated:
                self.beat_repo.replace_beats_for_script(script_id, beats)
                # Re-audit updated beats to verify grounding
                updated_payload = [
                    {
                        "beat_index": b.beat_index,
                        "beat_type": b.beat_type,
                        "spoken_script": b.spoken_script,
                    }
                    for b in beats
                ]
                raw_claims = await self.llm_provider.audit_claims(updated_payload, article_text)

        # Convert raw_claims to ScriptClaimAudit entities
        audit_models: list[ScriptClaimAudit] = []
        max_beats = max(1, len(beats))
        for c in raw_claims:
            raw_idx = int(c.get("beat_index", 1))
            clamped_idx = max(1, min(max_beats, raw_idx))
            audit_models.append(
                ScriptClaimAudit(
                    script_id=script_id,
                    beat_index=clamped_idx,
                    claim_text=str(c.get("claim_text", "")).strip(),
                    verified_citation=c.get("verified_citation"),
                    source_verbatim_quote=c.get("source_verbatim_quote"),
                    is_grounded=bool(c.get("is_grounded", False)),
                    audit_notes=c.get("audit_notes"),
                )
            )

        saved_audits = self.audit_repo.replace_audits_for_script(script_id, audit_models)
        summary = self.audit_repo.get_grounded_summary(script_id)

        # Update Script status
        grounding_threshold = getattr(settings, "SCRIPT_GROUNDING_THRESHOLD", 0.75)
        if summary.get("is_fully_grounded") or summary.get("grounding_ratio", 0.0) >= grounding_threshold:
            script = self.script_repo.update_status(script_id, "audited") or script
        else:
            script = self.script_repo.update_status(script_id, "rejected") or script

        logger.info(
            f"Fact check audit complete for script {script_id}: ratio={summary.get('grounding_ratio')} "
            f"({summary.get('grounded_claims')}/{summary.get('total_claims')} grounded) status={script.status}"
        )
        return script, saved_audits, summary
