import json
from typing import Any

# ==============================================================================
# STAGE 2: CANDIDATE SCREENING PROMPT
# ==============================================================================

SCREENING_SYSTEM_PROMPT = (
    "You are an executive technology editor and news curation engine. "
    "Your objective is to identify high-signal technology breakthroughs and filter out noise. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_screening_prompt(
    candidates: list[dict[str, Any]],
    top_k: int = 10,
    topic_filter: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the system and user prompt for Stage 2 candidate screening with client alignment."""
    client_context = ""
    if topic_filter:
        industries = topic_filter.get("industries", "")
        keywords = topic_filter.get("focus_keywords", "")
        excluded = topic_filter.get("excluded_keywords", "")
        client_context = (
            f"TARGET CLIENT EDITORIAL MANDATE:\n"
            f"- Target Industry / Sector: {industries or 'All Emerging AI & Enterprise Automation'}\n"
            f"- Priority Focus Keywords & Themes: {keywords or 'High utility technology'}\n"
            f"- Excluded / Irrelevant Topics: {excluded or 'None'}\n\n"
            "INSTRUCTION: You must strictly evaluate each candidate against this client mandate. "
            "Strongly prioritize and elevate articles matching the focus keywords and industry. "
            "Deprioritize or exclude irrelevant articles, generic PR noise, or excluded topics.\n\n"
        )

    user_prompt = (
        "You are an executive tech editor and business intelligence curation engine.\n"
        f"{client_context}"
        f"Review all the following news articles and select the top {top_k} most relevant and impactful stories for the client:\n\n"
        f"Input Articles:\n{json.dumps(candidates, indent=2)}\n\n"
        "Respond ONLY with a JSON object in this exact schema:\n"
        "{\n"
        '  "screened": [\n'
        '    {\n'
        '      "article_id": "string",\n'
        '      "title": "string",\n'
        '      "url": "string",\n'
        '      "relevance_score": 0.0 to 1.0,\n'
        '      "screening_reason": "concise 1-sentence justification explaining relevance to client mandate"\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    return SCREENING_SYSTEM_PROMPT, user_prompt


# ==============================================================================
# STAGE 3: DUAL-SOURCE VERIFICATION PROMPT
# ==============================================================================

VERIFICATION_SYSTEM_PROMPT = (
    "You are an objective investigative fact-checking editor. "
    "Your task is to analyze claims across independent sources for agreement or contradiction. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_verification_prompt(
    primary_title: str,
    primary_text: str,
    secondary_title: str,
    secondary_text: str,
    max_chars: int = 2500,
) -> tuple[str, str]:
    """Build the system and user prompt for Stage 3 dual-source corroboration check."""
    user_prompt = (
        "You are a meticulous fact-checking editor. Compare the factual claims between these two independent news reports.\n"
        "Check for agreement on core facts: who, what happened, company decisions, dates, technical claims, and figures.\n\n"
        f"PRIMARY ARTICLE:\nTitle: {primary_title}\nText: {primary_text[:max_chars]}\n\n"
        f"SECONDARY ARTICLE:\nTitle: {secondary_title}\nText: {secondary_text[:max_chars]}\n\n"
        "Compute an agreement score between 0.00 and 1.00.\n"
        "- 0.75 to 1.00: Strong corroboration of core facts.\n"
        "- Below 0.75: Substantial contradictions, unverified claims, or unrelated stories.\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "agreement_score": 0.0 to 1.0,\n'
        '  "is_verified": true/false,\n'
        '  "corroboration_notes": "1-2 sentence audit summary explaining agreement or discrepancies"\n'
        "}"
    )
    return VERIFICATION_SYSTEM_PROMPT, user_prompt


# ==============================================================================
# STAGE 4: BUSINESS UTILITY SCORING PROMPT
# ==============================================================================

SCORING_SYSTEM_PROMPT = (
    "You are an executive technology strategist evaluating AI developments for strategic impact. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_scoring_prompt(
    title: str,
    full_text: str,
    profile_criteria: dict[str, Any] | None = None,
    max_chars: int = 3000,
) -> tuple[str, str]:
    """Build the system and user prompt for Stage 4 executive utility scoring."""
    criteria_context = ""
    if profile_criteria:
        criteria_context = f"Target Client Criteria:\n{json.dumps(profile_criteria, indent=2)}\n\n"

    user_prompt = (
        "You are an executive technology strategist evaluating an AI news story for video briefing production.\n"
        f"{criteria_context}"
        f"ARTICLE TITLE: {title}\n"
        f"ARTICLE CONTENT: {full_text[:max_chars]}\n\n"
        "Score the article on each of the four dimensions from 0.00 to 1.00:\n"
        "1. actionability (0.0 to 1.0): Can leaders make concrete strategic, technical, or operational decisions?\n"
        "2. economic_impact (0.0 to 1.0): Does it impact costs, market valuations, vendor ecosystems, or efficiency?\n"
        "3. regulatory_impact (0.0 to 1.0): Does it involve legal compliance, copyright, risk, or government policy?\n"
        "4. novelty (0.0 to 1.0): Is this a fundamental breakthrough or routine release?\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "actionability": 0.0 to 1.0,\n'
        '  "economic_impact": 0.0 to 1.0,\n'
        '  "regulatory_impact": 0.0 to 1.0,\n'
        '  "novelty": 0.0 to 1.0,\n'
        '  "reasoning": "2-sentence strategic rationale for why this story matters to executives"\n'
        "}"
    )
    return SCORING_SYSTEM_PROMPT, user_prompt


# ==============================================================================
# PHASE 2: SCRIPTWRITING & FACT-CHECKING AUDITOR PROMPTS
# ==============================================================================

SCRIPTWRITING_SYSTEM_PROMPT = (
    "You are an elite short-form executive scriptwriter for technology business leaders. "
    "You transform complex AI news breakthroughs into authoritative, high-converting 60-90 second video scripts. "
    "Every factual claim must be strictly grounded in the provided article text. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_scriptwriting_prompt(
    article_title: str,
    full_text: str,
    persona: dict[str, Any],
    topic_filter: dict[str, Any] | None = None,
    max_chars: int = 4000,
) -> tuple[str, str]:
    """Build the system and user prompt for 5-beat grounded scriptwriting."""
    persona_role = persona.get("persona_role", "AI Chief of Staff")
    tone_of_voice = persona.get("tone_of_voice", "Concise, analytical, authoritative")
    target_audience = persona.get("target_audience", "Business owners, tech executives, and startup founders")
    default_cta = persona.get("default_cta", "Follow for daily executive AI updates.")

    filter_context = ""
    if topic_filter:
        industries = topic_filter.get("industries", "[]")
        focus = topic_filter.get("focus_keywords", "[]")
        filter_context = f"\nClient Focus Areas: Industries={industries}, Keywords={focus}\n"

    user_prompt = (
        f"You are writing a 60–90 second executive video briefing script as a {persona_role}.\n"
        f"Tone of voice: {tone_of_voice}\n"
        f"Target audience: {target_audience}\n"
        f"Custom Call to Action: {default_cta}\n"
        f"{filter_context}\n"
        f"ARTICLE TITLE: {article_title}\n"
        f"ARTICLE FULL TEXT:\n{full_text[:max_chars]}\n\n"
        "STRICT STRUCTURE REQUIREMENT: Exactly 5 beats totaling 60 to 90 seconds:\n"
        "1. Beat 1 (HOOK, ~10s, 0-10s): Bold, disruptive opening statement stopping the scroll. Speaks directly to the target audience.\n"
        "2. Beat 2 (CONTEXT, ~15s, 10-25s): Grounded background. What was the status quo or pain point before this breakthrough?\n"
        "3. Beat 3 (CORE_SHIFT, ~25s, 25-50s): The technical or market breakthrough. The specific announcement, figures, benchmarks, or product launch.\n"
        "4. Beat 4 (BUSINESS_IMPACT, ~20s, 50-70s): Economic, strategic, and competitive consequences. What does this mean for budgets, margins, and tech roadmaps?\n"
        "5. Beat 5 (CTA, ~15s, 70-90s): Concrete strategic takeaway and the business owner's customized call to action.\n\n"
        "RULES:\n"
        "- Spoken text must sound natural for a teleprompter, direct and punchy.\n"
        "- Do NOT hallucinate statistics or dates not in the article.\n"
        "- Visual directives should use camera cues: 'PRESENTER_CAMERA_A', 'PRESENTER_CAMERA_B_SPLIT', 'PRESENTER_CAMERA_A_PUNCH_IN', 'WHITEBOARD_GRAPHIC'.\n"
        "- Whiteboard directive: 1-sentence prompt for animated bullet points or diagram cues (or null).\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "title": "Compelling video title",\n'
        '  "persona_role": "string",\n'
        '  "total_estimated_duration_sec": 75,\n'
        '  "call_to_action": "string",\n'
        '  "beats": [\n'
        "    {\n"
        '      "beat_index": 1,\n'
        '      "beat_type": "HOOK",\n'
        '      "spoken_script": "exact teleprompter spoken words",\n'
        '      "visual_directive": "PRESENTER_CAMERA_A",\n'
        '      "whiteboard_directive": "optional motion graphic cue or null",\n'
        '      "estimated_seconds": 10\n'
        "    },\n"
        "    {\n"
        '      "beat_index": 2,\n'
        '      "beat_type": "CONTEXT",\n'
        '      "spoken_script": "...",\n'
        '      "visual_directive": "PRESENTER_CAMERA_A",\n'
        '      "whiteboard_directive": "...",\n'
        '      "estimated_seconds": 15\n'
        "    },\n"
        "    {\n"
        '      "beat_index": 3,\n'
        '      "beat_type": "CORE_SHIFT",\n'
        '      "spoken_script": "...",\n'
        '      "visual_directive": "PRESENTER_CAMERA_B_SPLIT",\n'
        '      "whiteboard_directive": "...",\n'
        '      "estimated_seconds": 25\n'
        "    },\n"
        "    {\n"
        '      "beat_index": 4,\n'
        '      "beat_type": "BUSINESS_IMPACT",\n'
        '      "spoken_script": "...",\n'
        '      "visual_directive": "PRESENTER_CAMERA_A_PUNCH_IN",\n'
        '      "whiteboard_directive": "...",\n'
        '      "estimated_seconds": 20\n'
        "    },\n"
        "    {\n"
        '      "beat_index": 5,\n'
        '      "beat_type": "CTA",\n'
        '      "spoken_script": "...",\n'
        '      "visual_directive": "PRESENTER_CAMERA_A",\n'
        '      "whiteboard_directive": null,\n'
        '      "estimated_seconds": 15\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    return SCRIPTWRITING_SYSTEM_PROMPT, user_prompt


CLAIM_AUDIT_SYSTEM_PROMPT = (
    "You are an adversarial claim-level fact-checking auditor. "
    "Your objective is to deconstruct short-form video scripts into atomic factual assertions and verify each assertion against the source text. "
    "Do NOT assume or fabricate evidence. A claim is grounded ONLY if the article explicitly contains a verbatim quote or direct factual confirmation. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_claim_audit_prompt(
    beats: list[dict[str, Any]],
    full_text: str,
    max_chars: int = 4000,
) -> tuple[str, str]:
    """Build the system and user prompt for claim-level factual grounding audit."""
    beats_json = json.dumps(
        [
            {
                "beat_index": b.get("beat_index"),
                "beat_type": b.get("beat_type"),
                "spoken_script": b.get("spoken_script"),
            }
            for b in beats
        ],
        indent=2,
    )

    user_prompt = (
        "You are an adversarial fact-checker. Extract every atomic factual assertion from the script beats below.\n"
        "Atomic factual assertions include: metrics, percentage shifts, model names, pricing, dates, company actions, and claims.\n"
        "Cross-check each claim against the SOURCE ARTICLE.\n\n"
        f"SCRIPT BEATS:\n{beats_json}\n\n"
        f"SOURCE ARTICLE FULL TEXT:\n{full_text[:max_chars]}\n\n"
        "VERIFICATION CRITERIA:\n"
        "- If a claim is explicitly supported by the article, provide the verbatim source quote in 'source_verbatim_quote' and set 'is_grounded': true.\n"
        "- If a claim is an unverified deduction, marketing exaggeration, or contradicted by the article, set 'is_grounded': false and 'source_verbatim_quote': null.\n"
        "- Mention which paragraph/section in 'verified_citation'.\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "claims": [\n'
        "    {\n"
        '      "beat_index": 1,\n'
        '      "claim_text": "Atomic factual assertion",\n'
        '      "verified_citation": "Source section or paragraph context",\n'
        '      "source_verbatim_quote": "Exact verbatim quote from the article or null",\n'
        '      "is_grounded": true,\n'
        '      "audit_notes": "1-sentence audit verification note"\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    return CLAIM_AUDIT_SYSTEM_PROMPT, user_prompt


REVISION_SYSTEM_PROMPT = (
    "You are an executive video script editor. "
    "Your job is to rewrite an ungrounded or speculative script beat so that every statement is 100% backed by verbatim facts from the source article, while preserving tone and duration. "
    "You must respond ONLY in strict, valid JSON matching the requested schema."
)


def get_revision_prompt(
    beat: dict[str, Any],
    ungrounded_claims: list[dict[str, Any]],
    full_text: str,
    persona: dict[str, Any],
    max_chars: int = 4000,
) -> tuple[str, str]:
    """Build prompt for revising a beat that contains ungrounded claims."""
    user_prompt = (
        f"A script beat contains ungrounded or hallucinated claims.\n"
        f"Persona Role: {persona.get('persona_role', 'AI Chief of Staff')}\n"
        f"Tone: {persona.get('tone_of_voice', 'Concise, analytical')}\n\n"
        f"CURRENT BEAT:\n{json.dumps(beat, indent=2)}\n\n"
        f"UNGROUNDED CLAIMS DETECTED:\n{json.dumps(ungrounded_claims, indent=2)}\n\n"
        f"SOURCE ARTICLE FULL TEXT:\n{full_text[:max_chars]}\n\n"
        "INSTRUCTION: Rewrite the spoken script of this beat to eliminate speculative or unverified claims, replacing them with strictly verified facts from the source article. Maintain the target duration and style.\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "spoken_script": "rewritten teleprompter text strictly grounded in source",\n'
        '  "visual_directive": "PRESENTER_CAMERA_...",\n'
        '  "whiteboard_directive": "optional directive or null",\n'
        '  "estimated_seconds": 15,\n'
        '  "revision_notes": "brief note on what was corrected"\n'
        "}"
    )
    return REVISION_SYSTEM_PROMPT, user_prompt
