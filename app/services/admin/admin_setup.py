import asyncio
from datetime import datetime, timezone
import uuid
from typing import Any, Optional
from fastapi import FastAPI
from app.core.log import logger
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette_admin import action
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.exceptions import FormValidationError
from starlette_admin.fields import URLField
from starlette_admin.views import CustomView
from sqlmodel import Session, select


class TimezoneAwareModelView(ModelView):
    """Base ModelView ensuring all naive datetimes submitted via admin forms receive UTC timezone."""

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        for k, v in list(data.items()):
            if isinstance(v, datetime) and not v.tzinfo:
                data[k] = v.replace(tzinfo=timezone.utc)
        await super().before_create(request, data, obj)

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        for k, v in list(data.items()):
            if isinstance(v, datetime) and not v.tzinfo:
                data[k] = v.replace(tzinfo=timezone.utc)
        await super().before_edit(request, data, obj)

from app.core.config import settings
from app.core.database import engine, get_session
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile, ClientTopicFilter
from app.models.media import RenderedVideo
from app.models.news import Article, ArticleScore, ArticleVerification, NewsSource
from app.models.script import Script, ScriptBeat, ScriptClaimAudit
from app.services.media.pipeline import VideoAssemblyService
from app.services.scripting.auditor import FactCheckingAuditorService
from app.services.scripting.pipeline import ScriptingPipeline


class AdminAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        if password == settings.ADMIN_AUTH_SECRET:
            request.session.update({"admin_user": username})
            return response
        raise FormValidationError({"password": "Invalid admin credentials"})

    async def is_authenticated(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None

    def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        username = request.session.get("admin_user")
        if username:
            return AdminUser(username=username)
        return None

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


class DailyWinnerView(CustomView):
    """Custom view presenting today's elected winner with full text and score audits."""

    def __init__(self, path: str = "/winner", add_to_menu: bool = True) -> None:
        super().__init__(
            label="Daily Winner",
            icon="fa fa-trophy",
            path=path,
            template_path="winner.html",
            add_to_menu=add_to_menu,
        )

    async def render(self, request: Request, templates: Jinja2Templates) -> Response:
        with get_session() as session:
            client_id_param = request.query_params.get("client_id")
            selected_client_id: uuid.UUID | None = None
            if client_id_param and client_id_param.lower() not in ("all", "none", ""):
                try:
                    selected_client_id = uuid.UUID(client_id_param)
                except ValueError:
                    selected_client_id = None

            statement = (
                select(ArticleScore)
                .where(ArticleScore.is_selected == True)  # noqa: E712
            )
            if selected_client_id:
                statement = statement.where(ArticleScore.client_id == selected_client_id)
            statement = statement.order_by(ArticleScore.composite_score.desc())

            score = session.exec(statement).first()
            article: Article | None = None
            if score:
                article = session.get(Article, score.article_id)
            else:
                article = session.exec(
                    select(Article).where(Article.status == "selected").order_by(Article.created_at.desc())
                ).first()

            verif: ArticleVerification | None = None
            source: NewsSource | None = None
            if article:
                verif = session.exec(
                    select(ArticleVerification).where(ArticleVerification.article_id == article.id)
                ).first()
                if not score:
                    score = session.exec(
                        select(ArticleScore).where(ArticleScore.article_id == article.id)
                    ).first()
                if article.source_id:
                    source = session.get(NewsSource, article.source_id)

            from app.repositories.client_repo import ClientProfileRepository
            client_repo = ClientProfileRepository(session)
            active_clients = list(client_repo.get_active_clients())

            return templates.TemplateResponse(
                request=request,
                name=self.template_path,
                context={
                    "request": request,
                    "title": "Daily Winner",
                    "article": article,
                    "score": score,
                    "verification": verif,
                    "source": source,
                    "active_clients": active_clients,
                    "selected_client_id": str(selected_client_id) if selected_client_id else "",
                },
            )


class ArticleAdminView(TimezoneAwareModelView):
    fields = ["title", "client", "source", "status", "url", "summary", "full_text", "published_at", "created_at"]
    exclude_fields_from_list = ["full_text", "summary"]
    exclude_fields_from_create = ["created_at"]
    exclude_fields_from_edit = ["created_at"]
    searchable_fields = ["title", "summary"]
    sortable_fields = ["status", "created_at", "published_at"]
    fields_default_sort = ["status:desc", "created_at:desc"]
    page_size = 25

    @action(
        name="generate_script",
        text="Generate Grounded Script",
        confirmation="Generate a 5-beat grounded script for the selected article(s)?",
        submit_btn_text="Generate",
        submit_btn_class="btn-success",
        icon_class="fa fa-scroll",
    )
    async def generate_script_action(self, request: Request, pks: list[Any]) -> str:
        from app.repositories.client_repo import ClientProfileRepository
        from app.repositories.news_repo import ArticleRepository

        article_ids = [uuid.UUID(str(pk)) for pk in pks]

        async def _bg_generate(art_ids: list[uuid.UUID]) -> None:
            with Session(engine) as session:
                pipeline = ScriptingPipeline(session)
                client_repo = ClientProfileRepository(session)
                art_repo = ArticleRepository(session)
                active_clients = list(client_repo.get_active_clients())
                for art_id in art_ids:
                    try:
                        article = art_repo.get_by_id(art_id)
                        if article and article.client_id:
                            await pipeline.generate_and_audit(article_id=art_id, client_id=article.client_id, auto_audit=True)
                        elif active_clients:
                            for cl in active_clients:
                                await pipeline.generate_and_audit(article_id=art_id, client_id=cl.id, auto_audit=True)
                        else:
                            await pipeline.generate_and_audit(article_id=art_id, client_id=None, auto_audit=True)
                    except Exception as exc:
                        logger.error(f"Admin background script generation failed for article {art_id}: {exc}")

        asyncio.create_task(_bg_generate(article_ids))
        return f"Script generation and fact-checking started in background for {len(article_ids)} article(s)! Refresh the Scripts tab shortly."


class ArticleScoreAdminView(TimezoneAwareModelView):
    fields = [
        "article",
        "composite_score",
        "is_selected",
        "actionability",
        "economic_impact",
        "regulatory_impact",
        "novelty",
        "reasoning",
        "scored_at",
    ]
    exclude_fields_from_create = ["scored_at"]
    exclude_fields_from_edit = ["scored_at"]
    sortable_fields = ["composite_score", "is_selected", "scored_at"]
    fields_default_sort = ["is_selected:desc", "composite_score:desc"]
    page_size = 25


class ArticleVerificationAdminView(TimezoneAwareModelView):
    fields = [
        "article",
        "is_verified",
        "agreement_score",
        "secondary_source",
        "secondary_url",
        "corroboration_notes",
        "checked_at",
    ]
    exclude_fields_from_create = ["checked_at"]
    exclude_fields_from_edit = ["checked_at"]
    sortable_fields = ["is_verified", "agreement_score", "checked_at"]
    fields_default_sort = ["is_verified:desc", "agreement_score:desc"]
    page_size = 25


class ClientProfileAdminView(TimezoneAwareModelView):
    fields = ["name", "slug", "is_active", "created_at", "updated_at"]
    exclude_fields_from_create = ["created_at", "updated_at"]
    exclude_fields_from_edit = ["created_at", "updated_at"]
    searchable_fields = ["name", "slug"]
    sortable_fields = ["name", "is_active", "created_at"]
    fields_default_sort = ["created_at:desc"]
    page_size = 25


class ClientPersonaAdminView(TimezoneAwareModelView):
    fields = ["client", "persona_role", "tone_of_voice", "target_audience", "default_cta"]
    searchable_fields = ["persona_role", "tone_of_voice", "target_audience"]
    page_size = 25


class ClientTopicFilterAdminView(TimezoneAwareModelView):
    fields = [
        "client",
        "industries",
        "focus_keywords",
        "excluded_keywords",
        "weight_actionability",
        "weight_economic",
        "weight_regulatory",
        "weight_novelty",
    ]
    page_size = 25


class ScriptAdminView(TimezoneAwareModelView):
    fields = [
        "title",
        "article",
        "client",
        "persona_role",
        "total_estimated_duration_sec",
        "call_to_action",
        "status",
        "created_at",
    ]
    exclude_fields_from_create = ["created_at"]
    exclude_fields_from_edit = ["created_at"]
    searchable_fields = ["title", "persona_role", "status"]
    sortable_fields = ["status", "created_at", "total_estimated_duration_sec"]
    fields_default_sort = ["created_at:desc"]
    page_size = 25

    @action(
        name="re_audit",
        text="Re-Audit Grounding",
        confirmation="Re-run claim fact-checking and critic reflection loop?",
        submit_btn_text="Re-Audit",
        submit_btn_class="btn-primary",
        icon_class="fa fa-balance-scale",
    )
    async def re_audit_action(self, request: Request, pks: list[Any]) -> str:
        script_ids = [uuid.UUID(str(pk)) for pk in pks]

        async def _bg_audit(s_ids: list[uuid.UUID]) -> None:
            with get_session() as session:
                auditor = FactCheckingAuditorService(session)
                for s_id in s_ids:
                    try:
                        await auditor.audit_script(script_id=s_id, auto_revise=True)
                    except Exception as exc:
                        logger.error(f"Admin background re-audit failed for script {s_id}: {exc}")

        asyncio.create_task(_bg_audit(script_ids))
        return f"Fact-checking re-audit started in background for {len(script_ids)} script(s)! Refresh shortly."

    @action(
        name="render_video",
        text="Render 9:16 Video",
        confirmation="Render vertical short-form MP4 video with neural voice and subtitles for selected script(s)?",
        submit_btn_text="Render Video",
        submit_btn_class="btn-success",
        icon_class="fa fa-film",
    )
    async def render_video_action(self, request: Request, pks: list[Any]) -> str:
        service = VideoAssemblyService()
        for pk in pks:
            s_id = uuid.UUID(str(pk))

            async def _bg_render(target_id: uuid.UUID) -> None:
                with get_session() as session:
                    try:
                        logger.info(f"Admin: Background video rendering started for script {target_id}...")
                        await service.render_video(script_id=target_id, session=session)
                        logger.info(f"Admin: Background video rendering finished for script {target_id}.")
                    except Exception as exc:
                        logger.error(f"Admin: Background video render failed for {target_id}: {exc}")

            asyncio.create_task(_bg_render(s_id))

        return f"Video rendering started in background for {len(pks)} script(s)! The Admin UI will not freeze. Check the 'Rendered Videos' tab in ~1 minute."


class ScriptBeatAdminView(TimezoneAwareModelView):
    fields = [
        "script",
        "beat_index",
        "beat_type",
        "spoken_script",
        "visual_directive",
        "whiteboard_directive",
        "estimated_seconds",
    ]
    searchable_fields = ["spoken_script", "beat_type"]
    sortable_fields = ["beat_index", "estimated_seconds"]
    fields_default_sort = ["beat_index:asc"]
    page_size = 25


class ScriptClaimAuditAdminView(TimezoneAwareModelView):
    fields = [
        "script",
        "beat_index",
        "claim_text",
        "is_grounded",
        "source_verbatim_quote",
        "verified_citation",
        "audit_notes",
    ]
    searchable_fields = ["claim_text", "source_verbatim_quote"]
    sortable_fields = ["is_grounded", "beat_index"]
    fields_default_sort = ["beat_index:asc"]
    page_size = 25


class ClientBrandKitAdminView(TimezoneAwareModelView):
    fields = [
        "client",
        "avatar_engine",
        "avatar_model_id",
        "voice_engine",
        "voice_id",
        "primary_hex",
        "accent_hex",
        "subtitle_highlight_hex",
        "background_hex",
        "font_family",
        "watermark_logo_url",
        "intro_bumper_url",
        "outro_bumper_url",
        "created_at",
        "updated_at",
    ]
    exclude_fields_from_create = ["created_at", "updated_at"]
    exclude_fields_from_edit = ["created_at", "updated_at"]
    searchable_fields = ["avatar_model_id", "voice_id", "font_family"]
    page_size = 25


class RenderedVideoAdminView(TimezoneAwareModelView):
    def can_create(self, request: Request) -> bool:
        return False

    fields = [
        "script",
        "client",
        "status",
        "duration_sec",
        "resolution",
        URLField("video_url", label="Video Preview", display_template="displays/video.html"),
        URLField("thumbnail_url", label="Thumbnail", display_template="displays/thumbnail.html"),
        URLField("audio_url", label="Audio Stem", display_template="displays/audio.html"),
        "social_caption",
        "created_at",
    ]
    exclude_fields_from_edit = ["created_at"]
    searchable_fields = ["status", "social_caption"]
    sortable_fields = ["status", "created_at", "duration_sec"]
    fields_default_sort = ["created_at:desc"]
    page_size = 25


def setup_admin(app: FastAPI) -> Admin:
    """Configure and mount StarletteAdmin dashboard at /admin."""
    auth_provider = AdminAuthProvider()
    admin = Admin(
        engine,
        title="AI News Admin",
        base_url="/admin",
        auth_provider=auth_provider,
        templates_dir="templates",
        index_view=DailyWinnerView(path="/", add_to_menu=False),
    )
    admin.add_view(DailyWinnerView(path="/winner", add_to_menu=True))
    admin.add_view(ArticleAdminView(Article, icon="fa fa-newspaper", label="Articles"))
    admin.add_view(ArticleVerificationAdminView(ArticleVerification, icon="fa fa-check-double", label="Verifications"))
    admin.add_view(ArticleScoreAdminView(ArticleScore, icon="fa fa-star", label="Scores"))
    admin.add_view(TimezoneAwareModelView(NewsSource, icon="fa fa-rss", label="News Sources"))
    admin.add_view(ClientProfileAdminView(ClientProfile, icon="fa fa-building", label="Clients"))
    admin.add_view(ClientPersonaAdminView(ClientPersona, icon="fa fa-user-tie", label="Personas"))
    admin.add_view(ClientTopicFilterAdminView(ClientTopicFilter, icon="fa fa-filter", label="Topic Filters"))
    admin.add_view(ClientBrandKitAdminView(ClientBrandKit, icon="fa fa-palette", label="Brand Kits"))
    admin.add_view(ScriptAdminView(Script, icon="fa fa-scroll", label="Scripts"))
    admin.add_view(ScriptBeatAdminView(ScriptBeat, icon="fa fa-list-ol", label="Script Beats"))
    admin.add_view(ScriptClaimAuditAdminView(ScriptClaimAudit, icon="fa fa-balance-scale", label="Claim Audits"))
    admin.add_view(RenderedVideoAdminView(RenderedVideo, icon="fa fa-video", label="Rendered Videos"))

    admin.mount_to(app)
    return admin
