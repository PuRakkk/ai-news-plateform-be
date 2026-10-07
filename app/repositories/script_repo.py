import uuid
from typing import Any, Sequence
from sqlmodel import Session, col, delete, func, select

from app.models.script import Script, ScriptBeat, ScriptClaimAudit
from app.repositories.base import BaseRepository


class ScriptRepository(BaseRepository[Script]):
    def __init__(self, session: Session) -> None:
        super().__init__(Script, session)

    def get_latest_by_article(
        self, article_id: uuid.UUID, client_id: uuid.UUID | None = None
    ) -> Script | None:
        statement = (
            select(Script)
            .where(Script.article_id == article_id, Script.client_id == client_id)
            .order_by(col(Script.created_at).desc())
        )
        return self.session.exec(statement).first()

    def list_scripts(
        self,
        client_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Script]:
        statement = select(Script)
        if client_id is not None:
            statement = statement.where(Script.client_id == client_id)
        if status:
            statement = statement.where(Script.status == status)

        statement = statement.order_by(col(Script.created_at).desc()).offset(skip).limit(limit)
        return self.session.exec(statement).all()

    def create_script(
        self,
        article_id: uuid.UUID,
        client_id: uuid.UUID | None,
        title: str,
        persona_role: str = "AI Chief of Staff",
        total_estimated_duration_sec: int = 75,
        call_to_action: str = "",
        status: str = "draft",
    ) -> Script:
        script = Script(
            article_id=article_id,
            client_id=client_id,
            title=title,
            persona_role=persona_role,
            total_estimated_duration_sec=total_estimated_duration_sec,
            call_to_action=call_to_action,
            status=status,
        )
        self.session.add(script)
        self.session.commit()
        self.session.refresh(script)
        return script

    def update_status(self, script_id: uuid.UUID, status: str) -> Script | None:
        script = self.session.get(Script, script_id)
        if not script:
            return None
        script.status = status
        self.session.add(script)
        self.session.commit()
        self.session.refresh(script)
        return script


class ScriptBeatRepository(BaseRepository[ScriptBeat]):
    def __init__(self, session: Session) -> None:
        super().__init__(ScriptBeat, session)

    def get_by_script_id(self, script_id: uuid.UUID) -> list[ScriptBeat]:
        statement = (
            select(ScriptBeat)
            .where(ScriptBeat.script_id == script_id)
            .order_by(col(ScriptBeat.beat_index).asc())
        )
        return list(self.session.exec(statement).all())

    def get_beats_by_script(self, script_id: uuid.UUID) -> list[ScriptBeat]:
        """Convenience alias for get_by_script_id."""
        return self.get_by_script_id(script_id)

    def replace_beats_for_script(
        self, script_id: uuid.UUID, beats: list[ScriptBeat]
    ) -> list[ScriptBeat]:
        existing_beats = self.get_by_script_id(script_id)
        existing_by_index = {b.beat_index: b for b in existing_beats}

        saved: list[ScriptBeat] = []
        for b in beats:
            if b.beat_index in existing_by_index:
                target = existing_by_index[b.beat_index]
                target.beat_type = b.beat_type
                target.spoken_script = b.spoken_script
                target.visual_directive = b.visual_directive
                target.whiteboard_directive = b.whiteboard_directive
                target.estimated_seconds = b.estimated_seconds
                self.session.add(target)
                saved.append(target)
            else:
                new_beat = ScriptBeat(
                    script_id=script_id,
                    beat_index=b.beat_index,
                    beat_type=b.beat_type,
                    spoken_script=b.spoken_script,
                    visual_directive=b.visual_directive,
                    whiteboard_directive=b.whiteboard_directive,
                    estimated_seconds=b.estimated_seconds,
                )
                self.session.add(new_beat)
                saved.append(new_beat)

        self.session.commit()
        for s in saved:
            self.session.refresh(s)
        return saved


class ScriptClaimAuditRepository(BaseRepository[ScriptClaimAudit]):
    def __init__(self, session: Session) -> None:
        super().__init__(ScriptClaimAudit, session)

    def get_by_script_id(self, script_id: uuid.UUID) -> list[ScriptClaimAudit]:
        statement = (
            select(ScriptClaimAudit)
            .where(ScriptClaimAudit.script_id == script_id)
            .order_by(col(ScriptClaimAudit.beat_index).asc())
        )
        return list(self.session.exec(statement).all())

    def replace_audits_for_script(
        self, script_id: uuid.UUID, audits: list[ScriptClaimAudit]
    ) -> list[ScriptClaimAudit]:
        existing = self.get_by_script_id(script_id)
        for e in existing:
            self.session.delete(e)
        self.session.commit()

        saved: list[ScriptClaimAudit] = []
        for a in audits:
            new_audit = ScriptClaimAudit(
                script_id=script_id,
                beat_index=a.beat_index,
                claim_text=a.claim_text,
                verified_citation=a.verified_citation,
                source_verbatim_quote=a.source_verbatim_quote,
                is_grounded=a.is_grounded,
                audit_notes=a.audit_notes,
            )
            self.session.add(new_audit)
            saved.append(new_audit)
        self.session.commit()
        for s in saved:
            self.session.refresh(s)
        return saved

    def get_grounded_summary(self, script_id: uuid.UUID) -> dict[str, Any]:
        audits = self.get_by_script_id(script_id)
        if not audits:
            return {"total_claims": 0, "grounded_claims": 0, "grounding_ratio": 0.0, "is_fully_grounded": False}
        total = len(audits)
        grounded = sum(1 for a in audits if a.is_grounded)
        ratio = round(grounded / total, 3) if total > 0 else 0.0
        return {
            "total_claims": total,
            "grounded_claims": grounded,
            "grounding_ratio": ratio,
            "is_fully_grounded": (grounded == total and total > 0),
        }
