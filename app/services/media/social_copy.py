from typing import Any

from app.models.client import ClientPersona, ClientProfile
from app.models.news import Article
from app.models.script import Script, ScriptBeat


def generate_social_caption(
    script: Script,
    article: Article | None,
    client: ClientProfile | None,
    persona: ClientPersona | None,
    beats: list[ScriptBeat] | None = None,
) -> str:
    """Generate structured multi-platform social media post copy for the rendered video."""
    title = script.title or (article.title if article else "AI Industry Shift")
    persona_role = persona.persona_role if persona else script.persona_role or "AI Executive"
    client_name = client.name if client else "AI News Daily"
    cta = script.call_to_action or (persona.default_cta if persona else "Follow for daily AI intelligence.")

    # Extract bullet points from beats if available
    bullets = []
    if beats:
        for b in sorted(beats, key=lambda x: x.beat_index):
            if b.beat_type in ("CORE_SHIFT", "BUSINESS_IMPACT") and b.spoken_script:
                first_sentence = b.spoken_script.split(".")[0].strip()
                if first_sentence:
                    bullets.append(f"• {first_sentence}.")
    if not bullets and article and article.summary:
        bullets = [f"• {article.summary[:140]}..."]

    bullet_block = "\n".join(bullets[:3]) if bullets else "• Major operational and economic shifts underway."

    source_name = article.source.name if (article and article.source) else "Verified Source"
    source_line = f"🔗 Source: {source_name} ({article.url})" if article and article.url else ""

    caption = f"""🚨 {title}

Perspective by {persona_role} ({client_name}):

Key Takeaways:
{bullet_block}

Why this matters:
The gap between AI research and enterprise implementation is closing faster than anticipated. Business leaders must evaluate workflow integration today.

👉 {cta}

{source_line}

#ArtificialIntelligence #TechLeadership #AIBriefing #Innovation #FutureOfWork #{client_name.replace(' ', '')}
""".strip()

    return caption
