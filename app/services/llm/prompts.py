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
            "EVALUATION INSTRUCTIONS:\n"
            "1. Evaluate each candidate's relevance to the target industry, workforce skills, automation, operations, safety, or modern enterprise technology.\n"
            "2. Strongly prioritize and elevate articles whose primary focus directly impacts the target industry and focus themes.\n"
            "3. If stories directly matching the niche trade/industry are limited or absent in this candidate batch, you MUST select the top highest-impact enterprise technology, automation, or workforce innovation breakthroughs that hold strategic intelligence value for operators and business leaders.\n"
            f"4. You MUST ALWAYS return between 3 and {top_k} candidates in the 'screened' list. NEVER return an empty screened list when input articles are provided.\n\n"
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
        "Score the article on each dimension from 0.00 to 1.00:\n"
        "1. client_relevance (0.0 to 1.0): Does this story directly impact the client's sector or provide critical strategic intelligence for business operations, workforce training, automation, or executive productivity? (0.8-1.0: direct core sector match; 0.5-0.7: workforce, operations, or technology breakthrough relevance; 0.1-0.4: low applicability).\n"
        "2. actionability (0.0 to 1.0): Can leaders make concrete strategic, technical, or operational decisions?\n"
        "3. economic_impact (0.0 to 1.0): Does it impact costs, market valuations, vendor ecosystems, or efficiency?\n"
        "4. regulatory_impact (0.0 to 1.0): Does it involve legal compliance, copyright, risk, or government policy?\n"
        "5. novelty (0.0 to 1.0): Is this a fundamental breakthrough or routine release?\n\n"
        "Respond ONLY with a JSON object in this schema:\n"
        "{\n"
        '  "client_relevance": 0.0 to 1.0,\n'
        '  "actionability": 0.0 to 1.0,\n'
        '  "economic_impact": 0.0 to 1.0,\n'
        '  "regulatory_impact": 0.0 to 1.0,\n'
        '  "novelty": 0.0 to 1.0,\n'
        '  "reasoning": "2-sentence strategic rationale explaining fit and impact for this client"\n'
        "}"
    )
    return SCORING_SYSTEM_PROMPT, user_prompt


# ==============================================================================
# PHASE 2: SCRIPTWRITING & FACT-CHECKING AUDITOR PROMPTS
# ==============================================================================

SCRIPTWRITING_SYSTEM_PROMPT = (
    "You are an elite short-form video scriptwriter and teleprompter copywriter. "
    "You transform complex breakthroughs and verified news into authoritative, high-converting "
    "60-90 second presenter video scripts delivered by a digital video avatar. "
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
    """Build the system and user prompt for 5-beat grounded scriptwriting tailored to the client profile."""
    client_name = persona.get("client_name") or ""
    persona_role = persona.get("persona_role", "Executive Presenter")
    tone_of_voice = persona.get("tone_of_voice", "Concise, analytical, authoritative")
    target_audience = persona.get("target_audience", "Industry professionals, business owners, and operators")
    default_cta = persona.get("default_cta", "Subscribe for daily industry updates.")

    if client_name:
        system_prompt = (
            f"You are an elite video scriptwriter and teleprompter copywriter for {client_name}. "
            "You transform verified industry news, policy announcements, and developments into engaging, "
            "authoritative 60-90 second presenter video scripts delivered on camera by a digital video avatar. "
            "Every factual claim must be strictly grounded in the provided article text. "
            "You must respond ONLY in strict, valid JSON matching the requested schema."
        )
    else:
        system_prompt = SCRIPTWRITING_SYSTEM_PROMPT

    filter_context = ""
    if topic_filter:
        industries = topic_filter.get("industries", "[]")
        focus = topic_filter.get("focus_keywords", "[]")
        filter_context = f"\nClient Focus Areas: Industries={industries}, Keywords={focus}\n"

    client_header = f"Client Organization: {client_name}\n" if client_name else ""

    user_prompt = (
        f"{client_header}"
        f"You are writing a 60–90 second presenter video briefing script as: {persona_role}.\n"
        f"Tone of voice: {tone_of_voice}\n"
        f"Target audience: {target_audience}\n"
        f"Custom Call to Action: {default_cta}\n"
        f"{filter_context}\n"
        f"ARTICLE TITLE: {article_title}\n"
        f"ARTICLE FULL TEXT:\n{full_text[:max_chars]}\n\n"
        "STRICT STRUCTURE REQUIREMENT: Exactly 5 progressive beats totaling 60 to 90 seconds:\n"
        "1. Beat 1 (HOOK, ~10s, 0-10s): Open directly as the on-camera presenter (e.g. natural greeting, introducing identity/organization where fitting) with a bold, scroll-stopping hook speaking directly to the target audience.\n"
        "2. Beat 2 (CONTEXT, ~15s, 10-25s): Grounded background. What is the current industry status quo, regulatory landscape, or operational context before this development?\n"
        "3. Beat 3 (CORE_SHIFT, ~25s, 25-50s): The core development or announcement. Specific policy change, program update, figures, or breakthrough strictly grounded in the article.\n"
        "4. Beat 4 (BUSINESS_IMPACT, ~20s, 50-70s): Practical workforce, operational, and industry impact. What does this mean on the ground for employers, workers, trainees, safety, or compliance?\n"
        "5. Beat 5 (CTA, ~15s, 70-90s): Supportive wrap-up (reinforcing confidence and brand ethos) and the customized call to action.\n\n"
        "PRESENTATION & TELEPROMPTER RULES (BROADCAST NEWS CADENCE):\n"
        "- SPOKEN NEWS DELIVERY, NOT ESSAY READING: Write as a real television anchor speaking directly to the viewer. Never write dry, academic, or formal book prose.\n"
        "- NATURAL CONTRACTIONS & CADENCE: Always use natural contractions ('we're', 'here's', 'it's', 'don't', 'you'll', 'they've'). Avoid stiff phrasing like 'do not', 'it is important to note', 'furthermore'.\n"
        "- BREATHING & RHYTHMIC PUNCTUATION: Use em dashes ('—') for dramatic pause beats, commas for breathing pauses, and short clauses (6-12 words per breath). This forces the speech engine to pause and speak with natural human inflection instead of robotic reading.\n"
        "- VERBAL SIGNPOSTS: Use conversational hooks to hold attention: 'Look at the numbers—', 'Here’s the real takeaway:', 'Why does this matter for your team?', 'Let’s break it down.'\n"
        "- FIRST-PERSON PRESENTER PRESENCE: Spoken text is read by a digital presenter (HeyGen avatar) on camera: write in warm, authoritative first person ('I', 'we', 'our team').\n"
        "- SEAMLESS FLOW: Connect each beat smoothly so all 5 beats sound like one seamless, high-energy executive broadcast.\n"
        "- STRICT FACT GROUNDING: Every claim, statistic, and policy must come strictly from the provided article text—do NOT invent numbers or facts.\n"
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
    return system_prompt, user_prompt


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
        "You are a rigorous factual accuracy auditor for executive video scripts.\n"
        "Your task is to identify and audit hard, verifiable factual assertions made in the script beats against the source article.\n\n"
        "WHAT COUNTS AS A FACTUAL ASSERTION (EXTRACT & AUDIT THESE):\n"
        "- Specific metrics, dollar amounts, performance percentages, and benchmark numbers.\n"
        "- Product names, model versions, feature announcements, and technical capabilities.\n"
        "- Company actions, regulatory decisions/approvals, partnerships, funding rounds, and dates.\n\n"
        "WHAT DOES NOT COUNT AS A FACTUAL ASSERTION (DO NOT EXTRACT THESE):\n"
        "- Conversational hooks, audience call-outs, and calls to action (e.g. 'Follow for daily briefings').\n"
        "- Presenter greetings, persona introductions, and brand statements (e.g. 'G\'day, I\'m Crystal from Major Training Group', 'Our team is here to support you'). These are presentation framing, NOT ungrounded external claims.\n"
        "- Subjective presenter commentary, rhetorical transitions, or high-level framing (e.g. 'This is a significant milestone', 'Leaders should prepare', 'Here is why this matters'). These are presentation style, NOT ungrounded facts.\n\n"
        f"SCRIPT BEATS:\n{beats_json}\n\n"
        f"SOURCE ARTICLE FULL TEXT:\n{full_text[:max_chars]}\n\n"
        "VERIFICATION CRITERIA:\n"
        "- If a factual claim is explicitly supported by the article, provide the verbatim source quote in 'source_verbatim_quote' and set 'is_grounded': true.\n"
        "- If a factual claim is fabricated, contradictory, or unsupported by the text, set 'is_grounded': false and 'source_verbatim_quote': null.\n"
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
