import asyncio
import tempfile
import uuid
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine
from app.models.client import ClientBrandKit, ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat
from app.repositories.client_repo import (
    ClientBrandKitRepository,
    ClientPersonaRepository,
    ClientProfileRepository,
)
from app.repositories.news_repo import ArticleRepository
from app.repositories.script_repo import ScriptBeatRepository, ScriptRepository
from app.services.media.canvas import render_beat_card
from app.services.media.compositor import VideoCompositor
from app.services.media.pipeline import VideoAssemblyService
from app.services.media.social_copy import generate_social_caption
from app.services.media.storage.local_storage import LocalStorageProvider
from app.services.media.subtitles import generate_ass_subtitles, hex_to_ass_color, sec_to_ass_time
from app.services.media.tts.base import TTSCue
from app.services.media.tts.mock_tts import MockTTSProvider


@pytest.fixture
def session():
    with Session(engine) as db_session:
        yield db_session


def test_hex_to_ass_and_time_formatting():
    # Test color conversion
    assert hex_to_ass_color("#10B981") == "&H0081B910&"
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF&"
    assert hex_to_ass_color("invalid") == "&H00FFFFFF&"

    # Test time conversion
    assert sec_to_ass_time(0.0) == "0:00:00.00"
    assert sec_to_ass_time(1.25) == "0:00:01.25"
    assert sec_to_ass_time(65.50) == "0:01:05.50"


def test_local_storage_operations():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = LocalStorageProvider(base_dir=tmp_dir, base_url="http://testserver/media")
        
        # Test bytes save
        test_data = b"video test content"
        url = storage.save_bytes(test_data, "test_folder/sample.txt", "text/plain")
        assert url == "http://testserver/media/test_folder/sample.txt"
        assert storage.file_exists("test_folder/sample.txt") is True

        # Test local path
        local_path = storage.get_local_path("test_folder/sample.txt")
        assert local_path is not None
        assert local_path.read_bytes() == test_data

        # Test delete
        assert storage.delete_file("test_folder/sample.txt") is True
        assert storage.file_exists("test_folder/sample.txt") is False


@pytest.mark.asyncio
async def test_mock_tts_synthesis():
    tts = MockTTSProvider(words_per_second=3.0)
    text = "Artificial intelligence is advancing at unprecedented velocity across software engineering."
    result = await tts.synthesize(text, voice_id="test-voice")

    assert result.duration_seconds > 0
    assert len(result.audio_bytes) > 0
    assert len(result.cues) > 0
    assert "00:00:" in result.srt_subtitles
    assert result.voice_id == "test-voice"


def test_ass_subtitle_generation():
    cues = [
        TTSCue(start_sec=0.0, end_sec=2.0, text="Breaking AI News Update"),
        TTSCue(start_sec=2.0, end_sec=4.5, text="Multi-agent architectures change everything"),
    ]
    # Default 16:9 widescreen
    ass_str = generate_ass_subtitles(
        cues=cues,
        font_family="Arial",
        highlight_hex="#F59E0B",
        primary_hex="#FFFFFF",
    )
    assert "[Script Info]" in ass_str
    assert "PlayResX: 1920" in ass_str
    assert "PlayResY: 1080" in ass_str
    assert "Breaking AI News" in ass_str
    assert "Update" in ass_str
    assert "&H000B9EF5&" in ass_str  # ASS representation of #F59E0B

    # Explicit 9:16 portrait
    ass_916 = generate_ass_subtitles(
        cues=cues,
        aspect_ratio="9:16",
    )
    assert "PlayResX: 1080" in ass_916
    assert "PlayResY: 1920" in ass_916


def test_beat_card_canvas_rendering():
    # Default 16:9 widescreen
    img = render_beat_card(
        beat_index=1,
        beat_type="HOOK",
        headline="Anthropic Announces Claude 3.5 Sonnet",
        content_text="Industry benchmark scores jump across coding and multimodal reasoning tasks.",
        client_name="Apex Logistics",
        persona_role="AI Chief of Staff",
        source_feed="TechCrunch",
        brand_colors={
            "background_hex": "#0F172A",
            "primary_hex": "#1E40AF",
            "accent_hex": "#F59E0B",
        },
    )
    assert img.size == (1920, 1080)
    assert img.mode == "RGB"

    # Explicit 9:16 portrait
    img_916 = render_beat_card(
        beat_index=1,
        beat_type="HOOK",
        headline="Anthropic Announces Claude 3.5 Sonnet",
        content_text="Industry benchmark scores jump across coding and multimodal reasoning tasks.",
        aspect_ratio="9:16",
    )
    assert img_916.size == (1080, 1920)


def test_social_caption_generator(session: Session):
    article = Article(
        title="Meta Unveils Llama 3 Open Weights",
        url="https://example.com/llama3",
        summary="State of the art open source models now rival proprietary closed models.",
        content_hash="hash_llama3",
    )
    client = ClientProfile(name="Nexus Logistics", slug=f"nexus-{uuid.uuid4().hex[:6]}")
    persona = ClientPersona(
        client_id=client.id,
        persona_role="Logistics AI Specialist",
        default_cta="Subscribe to our supply chain AI newsletter.",
    )
    script = Script(
        article_id=article.id,
        client_id=client.id,
        title="Open Source AI Rivals Closed Frontier Models",
        persona_role="Logistics AI Specialist",
        call_to_action="Follow for daily executive AI updates.",
    )
    beats = [
        ScriptBeat(
            script_id=script.id,
            beat_index=1,
            beat_type="HOOK",
            spoken_script="Meta just dropped Llama 3 and changed open source AI.",
            visual_directive="CAMERA_A",
        ),
        ScriptBeat(
            script_id=script.id,
            beat_index=2,
            beat_type="CORE_SHIFT",
            spoken_script="Cost per token has dropped by eighty percent for enterprise self-hosting.",
            visual_directive="CAMERA_B",
        ),
    ]

    caption = generate_social_caption(
        script=script,
        article=article,
        client=client,
        persona=persona,
        beats=beats,
    )

    assert "Meta Unveils Llama 3" in caption or "Open Source AI" in caption
    assert "Nexus Logistics" in caption
    assert "Logistics AI Specialist" in caption
    assert "#ArtificialIntelligence" in caption
    assert "Follow for daily executive AI updates." in caption


@pytest.mark.asyncio
async def test_video_assembly_end_to_end(session: Session):
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = LocalStorageProvider(base_dir=tmp_dir, base_url="http://testserver/media")
        tts = MockTTSProvider(words_per_second=3.0)
        compositor = VideoCompositor()
        service = VideoAssemblyService(storage=storage, tts=tts, compositor=compositor)

        # 1. Setup DB records
        uid_suffix = uuid.uuid4().hex[:6]
        art_repo = ArticleRepository(session)
        article = Article(
            title=f"OpenAI Unveils Autonomous Code Generation {uid_suffix}",
            url=f"https://example.com/news-{uid_suffix}",
            summary="Autonomous agents achieve 85% on benchmark coding tasks.",
            full_text="Autonomous agents now autonomously inspect repositories and fix bugs.",
            content_hash=f"hash_{uid_suffix}",
            status="selected",
        )
        article, _ = art_repo.create_if_not_exists(article)

        client_repo = ClientProfileRepository(session)
        client = client_repo.create_client(
            name=f"Vanguard Logistics AI {uid_suffix}",
            slug=f"vanguard-{uid_suffix}",
        )

        persona_repo = ClientPersonaRepository(session)
        persona_repo.upsert_persona(
            client_id=client.id,
            persona_role="Enterprise AI Architect",
            tone_of_voice="Analytical and decisive",
            target_audience="CTOs and Logistics Executives",
            default_cta="Follow Vanguard for daily enterprise AI intelligence.",
        )

        brand_repo = ClientBrandKitRepository(session)
        brand_repo.upsert_brand_kit(
            client_id=client.id,
            voice_engine="mock",
            voice_id="mock-voice",
            primary_hex="#1E40AF",
            accent_hex="#F59E0B",
            subtitle_highlight_hex="#10B981",
            background_hex="#0F172A",
            font_family="Arial",
        )

        script_repo = ScriptRepository(session)
        script = script_repo.create_script(
            article_id=article.id,
            client_id=client.id,
            title="OpenAI Releases Autonomous Code Agents",
            persona_role="Enterprise AI Architect",
            total_estimated_duration_sec=20,
            call_to_action="Follow Vanguard for daily enterprise AI intelligence.",
            status="audited",
        )

        beat_repo = ScriptBeatRepository(session)
        beats = [
            ScriptBeat(
                script_id=script.id,
                beat_index=1,
                beat_type="HOOK",
                spoken_script="OpenAI just changed software engineering forever.",
                visual_directive="PRESENTER_CAMERA_A",
                whiteboard_directive="Diagram of autonomous coding agent pipeline",
                estimated_seconds=4,
            ),
            ScriptBeat(
                script_id=script.id,
                beat_index=2,
                beat_type="CORE_SHIFT",
                spoken_script="Autonomous agents now resolve 85 percent of repository issues with no human intervention.",
                visual_directive="PRESENTER_CAMERA_B_SPLIT",
                whiteboard_directive="85% benchmark accuracy comparison bar chart",
                estimated_seconds=5,
            ),
            ScriptBeat(
                script_id=script.id,
                beat_index=3,
                beat_type="CTA",
                spoken_script="Follow Vanguard Logistics for daily enterprise AI updates.",
                visual_directive="PRESENTER_CAMERA_A",
                whiteboard_directive="Client logo and social handle follow badge",
                estimated_seconds=3,
            ),
        ]
        beat_repo.replace_beats_for_script(script.id, beats)

        # 2. Run video render
        video = await service.render_video(
            script_id=script.id,
            client_id=client.id,
            session=session,
        )

        assert video is not None
        assert video.script_id == script.id
        assert video.client_id == client.id
        assert video.status == "ready"
        assert video.resolution == "1920x1080"
        assert video.duration_sec > 0
        assert video.file_size_bytes > 0
        assert video.video_url.startswith("http://testserver/media/rendered/")
        assert video.audio_url.startswith("http://testserver/media/audio/")
        assert video.thumbnail_url.startswith("http://testserver/media/thumbnails/")
        assert video.social_caption is not None
        assert "Vanguard Logistics" in video.social_caption

        # Cleanup test records in child-to-parent order
        from sqlmodel import delete
        from app.models.media import RenderedVideo
        session.exec(delete(RenderedVideo).where(RenderedVideo.id == video.id))
        session.exec(delete(ScriptBeat).where(ScriptBeat.script_id == script.id))
        session.exec(delete(Script).where(Script.id == script.id))
        session.exec(delete(ClientBrandKit).where(ClientBrandKit.client_id == client.id))
        session.exec(delete(ClientPersona).where(ClientPersona.client_id == client.id))
        session.exec(delete(ClientProfile).where(ClientProfile.id == client.id))
        session.exec(delete(Article).where(Article.id == article.id))
        session.commit()


def test_media_api_endpoints(client: TestClient, session: Session):
    uid_suffix = uuid.uuid4().hex[:6]
    art_repo = ArticleRepository(session)
    article = Article(
        title=f"API Media Test Article {uid_suffix}",
        url=f"https://example.com/api-{uid_suffix}",
        summary="Testing video rendering API endpoint.",
        content_hash=f"hash_{uid_suffix}",
        status="selected",
    )
    article, _ = art_repo.create_if_not_exists(article)

    script_repo = ScriptRepository(session)
    script = script_repo.create_script(
        article_id=article.id,
        client_id=None,
        title="API Video Test Script",
        persona_role="AI Host",
        status="audited",
    )
    beat_repo = ScriptBeatRepository(session)
    beat_repo.replace_beats_for_script(
        script.id,
        [
            ScriptBeat(
                script_id=script.id,
                beat_index=1,
                beat_type="HOOK",
                spoken_script="This is a quick API video render test.",
                visual_directive="CAMERA_A",
                estimated_seconds=3,
            ),
        ],
    )

    # 1. Trigger render via API
    resp = client.post(
        "/api/v1/videos/render",
        json={
            "script_id": str(script.id),
            "client_id": None,
            "voice_id": "en-US-ChristopherNeural",
            "include_subtitles": True,
            "include_watermark": False,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "video" in data
    video_id = data["video"]["id"]
    assert data["video"]["script_id"] == str(script.id)
    assert data["video"]["status"] == "ready"

    # 2. Get video by ID
    get_resp = client.get(f"/api/v1/videos/{video_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == video_id

    # 3. Get video by Script ID
    script_resp = client.get(f"/api/v1/videos/script/{script.id}")
    assert script_resp.status_code == 200
    assert script_resp.json()["id"] == video_id

    # 4. List videos
    list_resp = client.get("/api/v1/videos/")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert any(v["id"] == video_id for v in items)

    # Cleanup API test records
    with Session(engine) as cleanup_session:
        from sqlmodel import delete
        from app.models.media import RenderedVideo
        cleanup_session.exec(delete(RenderedVideo).where(RenderedVideo.id == uuid.UUID(video_id)))
        cleanup_session.exec(delete(ScriptBeat).where(ScriptBeat.script_id == script.id))
        cleanup_session.exec(delete(Script).where(Script.id == script.id))
        cleanup_session.exec(delete(Article).where(Article.id == article.id))
        cleanup_session.commit()


@pytest.mark.asyncio
async def test_elevenlabs_provider_fallback_and_cues():
    from app.services.media.tts.elevenlabs_provider import ElevenLabsTTSProvider
    from app.services.media.tts.mock_tts import MockTTSProvider

    mock_fallback = MockTTSProvider()
    provider = ElevenLabsTTSProvider(api_key=None, fallback_provider=mock_fallback)

    # 1. Fallback behavior when API key is None
    res = await provider.synthesize("AI technology breakthrough transforms operations.")
    assert res.duration_seconds > 0
    assert len(res.audio_bytes) > 0

    # 2. Alignment cue building logic
    chars = ["H", "e", "l", "l", "o", " ", "w", "o", "r", "l", "d"]
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
    cues = provider._build_cues_from_alignment(chars, starts, ends)
    assert len(cues) > 0
    assert "Hello" in cues[0].text


@pytest.mark.asyncio
async def test_asset_resolver_security_and_local():
    from app.services.media.asset_resolver import AssetResolver

    with tempfile.TemporaryDirectory() as td:
        dest_dir = Path(td)
        resolver = AssetResolver()

        # 1. SSRF URL blocked
        ssrf_res = await resolver.resolve_asset("http://127.0.0.1:8080/secret", dest_dir, "test.png")
        assert ssrf_res is None

        # 2. Non-existent path returns None
        none_res = await resolver.resolve_asset(None, dest_dir, "none.png")
        assert none_res is None

        # 3. Direct local file resolved
        local_sample = dest_dir / "sample.png"
        local_sample.write_bytes(b"image data")
        resolved = await resolver.resolve_asset(str(local_sample), dest_dir, "resolved.png")
        assert resolved is not None
        assert resolved.exists()


def test_video_engine_factory():
    from app.services.media.engine import (
        BaseVideoEngine,
        DIDVideoEngine,
        HeyGenVideoEngine,
        MockVideoEngine,
        ProgrammaticVideoEngine,
        get_video_engine,
    )

    assert isinstance(get_video_engine("mock"), MockVideoEngine)
    assert isinstance(get_video_engine("programmatic"), ProgrammaticVideoEngine)
    assert isinstance(get_video_engine("heygen"), HeyGenVideoEngine)
    assert isinstance(get_video_engine("did"), DIDVideoEngine)
    assert isinstance(get_video_engine("unknown"), ProgrammaticVideoEngine)


@pytest.mark.asyncio
async def test_video_assembly_with_mock_engine(session: Session):
    uid_suffix = uuid.uuid4().hex[:6]
    art_repo = ArticleRepository(session)
    article = Article(
        title=f"Mock Engine Test Article {uid_suffix}",
        url=f"https://example.com/mock-{uid_suffix}",
        summary="Testing mock engine integration.",
        content_hash=f"hash_mock_{uid_suffix}",
        status="selected",
    )
    article, _ = art_repo.create_if_not_exists(article)

    script_repo = ScriptRepository(session)
    script = script_repo.create_script(
        article_id=article.id,
        client_id=None,
        title="Mock Video Test Script",
        persona_role="Tech Lead",
        status="audited",
    )
    beat_repo = ScriptBeatRepository(session)
    beat_repo.replace_beats_for_script(
        script.id,
        [
            ScriptBeat(
                script_id=script.id,
                beat_index=1,
                beat_type="HOOK",
                spoken_script="Testing mock engine output.",
                visual_directive="CAMERA_A",
                estimated_seconds=2,
            ),
        ],
    )

    service = VideoAssemblyService()
    rendered = await service.render_video(
        script_id=script.id,
        engine_type="mock",
        session=session,
    )
    assert rendered.status == "ready"
    assert rendered.duration_sec >= 1.0
    assert rendered.resolution == "1920x1080"
    assert rendered.thumbnail_url is not None

    # Cleanup test records in child-to-parent order
    from sqlmodel import delete
    from app.models.media import RenderedVideo
    session.exec(delete(RenderedVideo).where(RenderedVideo.id == rendered.id))
    session.exec(delete(ScriptBeat).where(ScriptBeat.script_id == script.id))
    session.exec(delete(Script).where(Script.id == script.id))
    session.exec(delete(Article).where(Article.id == article.id))
    session.commit()


@pytest.mark.asyncio
async def test_render_video_non_blocking_event_loop(session: Session):
    """Verify that video rendering executes asynchronously in worker threads without blocking the event loop."""
    uid_suffix = uuid.uuid4().hex[:6]
    art_repo = ArticleRepository(session)
    article = Article(
        title=f"Non-blocking Event Loop Test {uid_suffix}",
        url=f"https://example.com/nonblocking-{uid_suffix}",
        summary="Testing event loop responsiveness during video rendering.",
        content_hash=f"hash_nb_{uid_suffix}",
        status="selected",
    )
    article, _ = art_repo.create_if_not_exists(article)

    script_repo = ScriptRepository(session)
    script = script_repo.create_script(
        article_id=article.id,
        client_id=None,
        title="Non-blocking Video Render Test",
        persona_role="AI Anchor",
        status="audited",
    )
    beat_repo = ScriptBeatRepository(session)
    beat_repo.replace_beats_for_script(
        script.id,
        [
            ScriptBeat(
                script_id=script.id,
                beat_index=1,
                beat_type="HOOK",
                spoken_script="Testing event loop responsiveness while video encodes.",
                visual_directive="CAMERA_A",
                estimated_seconds=3,
            ),
        ],
    )

    heartbeat_ticks = 0
    stop_heartbeat = False

    async def heartbeat():
        nonlocal heartbeat_ticks
        while not stop_heartbeat:
            heartbeat_ticks += 1
            await asyncio.sleep(0.02)

    heartbeat_task = asyncio.create_task(heartbeat())

    service = VideoAssemblyService()
    try:
        rendered = await service.render_video(
            script_id=script.id,
            session=session,
        )
    finally:
        stop_heartbeat = True
        await heartbeat_task

    assert rendered.status == "ready"
    assert rendered.duration_sec > 0
    # Crucial assertion: the concurrent heartbeat task was able to progress multiple times
    # while the video rendering (Pillow + FFmpeg) was executing, proving the event loop was not blocked.
    assert heartbeat_ticks >= 3, f"Heartbeat did not tick sufficiently ({heartbeat_ticks} ticks); event loop was likely blocked!"

    # Cleanup test records
    from sqlmodel import delete
    from app.models.media import RenderedVideo
    session.exec(delete(RenderedVideo).where(RenderedVideo.id == rendered.id))
    session.exec(delete(ScriptBeat).where(ScriptBeat.script_id == script.id))
    session.exec(delete(Script).where(Script.id == script.id))
    session.exec(delete(Article).where(Article.id == article.id))
    session.commit()

