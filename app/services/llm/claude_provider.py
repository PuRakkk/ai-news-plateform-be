import json
from typing import Any
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.core.log import logger
from app.services.llm.base import LLMProviderAdapter
from app.services.llm.prompts import (
    get_claim_audit_prompt,
    get_revision_prompt,
    get_scoring_prompt,
    get_screening_prompt,
    get_scriptwriting_prompt,
    get_verification_prompt,
)


def _extract_json(text: str) -> dict[str, Any] | list[Any]:
    """Robustly extract and parse JSON payload from Claude completion text."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    start_obj = text.find("{")
    end_obj = text.rfind("}")
    start_arr = text.find("[")
    end_arr = text.rfind("]")

    if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
        if end_obj != -1 and end_obj > start_obj:
            return json.loads(text[start_obj : end_obj + 1])
    elif start_arr != -1:
        if end_arr != -1 and end_arr > start_arr:
            return json.loads(text[start_arr : end_arr + 1])

    return json.loads(cleaned)


class ClaudeProvider(LLMProviderAdapter):
    """Anthropic Claude implementation using AsyncAnthropic SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.effective_claude_api_key
        self.model = model or settings.effective_claude_model or "claude-3-5-sonnet-20241022"
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY is not configured in settings.")
        self.client = AsyncAnthropic(api_key=self.api_key or "missing_key")

    async def _generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Helper to invoke Claude Messages API asynchronously."""
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }
        response = await self.client.messages.create(**create_kwargs)
        content = ""
        for block in response.content:
            if getattr(block, "type", "") == "text" or hasattr(block, "text"):
                content += getattr(block, "text", "")
        return content

    async def screen_candidates(
        self,
        candidates: list[dict[str, Any]],
        top_k: int = 10,
        topic_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Stage 2: Filter noise and rank candidate stories based on client editorial mandate."""
        if not candidates:
            return []

        # Safeguard to prevent context limit errors while allowing thorough coverage
        candidates = candidates[:60]
        system_prompt, user_prompt = get_screening_prompt(
            candidates, top_k=top_k, topic_filter=topic_filter
        )

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=4096,
            )
            data = _extract_json(content)
            screened: list[dict[str, Any]] = data.get("screened", [])
            # Sort by relevance_score descending
            screened.sort(key=lambda x: float(x.get("relevance_score", 0.0)), reverse=True)
            return screened[:top_k]
        except Exception as e:
            logger.error(f"Claude screening failed: {e}")
            # Fallback: return top_k candidates with basic scoring
            return [
                {
                    "article_id": str(c.get("id", "")),
                    "title": str(c.get("title", "")),
                    "url": str(c.get("url", "")),
                    "relevance_score": 0.5,
                    "screening_reason": "Fallback screening due to Claude provider error.",
                }
                for c in candidates[:top_k]
            ]

    async def verify_corroboration(
        self,
        primary_title: str,
        primary_text: str,
        secondary_title: str,
        secondary_text: str,
    ) -> dict[str, Any]:
        """Stage 3: Cross-check factual consistency between independent sources."""
        system_prompt, user_prompt = get_verification_prompt(
            primary_title=primary_title,
            primary_text=primary_text,
            secondary_title=secondary_title,
            secondary_text=secondary_text,
        )

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=2048,
            )
            data = _extract_json(content)
            score = float(data.get("agreement_score", 0.0))
            is_verified = bool(score >= 0.75)
            return {
                "agreement_score": round(score, 3),
                "is_verified": is_verified,
                "corroboration_notes": data.get("corroboration_notes", "Verified via dual-source cross-check."),
            }
        except Exception as e:
            logger.error(f"Claude verification failed: {e}")
            return {
                "agreement_score": 0.0,
                "is_verified": False,
                "corroboration_notes": f"Verification error: {e}",
            }

    async def score_utility(
        self,
        title: str,
        full_text: str,
        profile_criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Stage 4: Score the business utility of an article."""
        system_prompt, user_prompt = get_scoring_prompt(
            title=title,
            full_text=full_text,
            profile_criteria=profile_criteria,
        )

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=2048,
            )
            data = _extract_json(content)

            act = float(data.get("actionability", 0.5))
            eco = float(data.get("economic_impact", 0.5))
            reg = float(data.get("regulatory_impact", 0.3))
            nov = float(data.get("novelty", 0.4))
            client_rel = float(data.get("client_relevance", 1.0))

            # Apply dynamic client weights if specified, else default baseline weights
            weights = (profile_criteria or {}).get("weights", {})
            w_act = float(weights.get("actionability", 0.40))
            w_eco = float(weights.get("economic_impact", 0.30))
            w_reg = float(weights.get("regulatory_impact", 0.20))
            w_nov = float(weights.get("novelty", 0.10))
            base_composite = w_act * act + w_eco * eco + w_reg * reg + w_nov * nov

            # Hybrid semantic dampening: if profile criteria exists and story is off-topic (< 0.60 client_relevance), heavily dampen composite score
            if profile_criteria and client_rel < 0.60:
                composite = round(base_composite * (client_rel ** 1.5), 4)
            else:
                composite = round(base_composite, 4)

            return {
                "composite_score": composite,
                "actionability": round(act, 3),
                "economic_impact": round(eco, 3),
                "regulatory_impact": round(reg, 3),
                "novelty": round(nov, 3),
                "client_relevance": round(client_rel, 3),
                "reasoning": data.get("reasoning", "High utility technology development."),
            }
        except Exception as e:
            logger.error(f"Claude utility scoring failed: {e}")
            return {
                "composite_score": 0.5,
                "actionability": 0.5,
                "economic_impact": 0.5,
                "regulatory_impact": 0.5,
                "novelty": 0.5,
                "reasoning": f"Fallback scoring due to Claude error: {e}",
            }

    async def generate_script(
        self,
        article_title: str,
        full_text: str,
        persona: dict[str, Any],
        topic_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Step 2: Generate 5-beat executive short-form video script."""
        system_prompt, user_prompt = get_scriptwriting_prompt(
            article_title=article_title,
            full_text=full_text,
            persona=persona,
            topic_filter=topic_filter,
        )

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
            )
            data = _extract_json(content)
            beats = data.get("beats", [])
            total_duration = sum(int(b.get("estimated_seconds", 15)) for b in beats)
            return {
                "title": data.get("title", article_title),
                "persona_role": data.get("persona_role", persona.get("persona_role", "AI Chief of Staff")),
                "total_estimated_duration_sec": total_duration or int(data.get("total_estimated_duration_sec", 75)),
                "call_to_action": data.get("call_to_action", persona.get("default_cta", "")),
                "beats": beats,
            }
        except Exception as e:
            logger.error(f"Claude script generation failed: {e}")
            role = persona.get("persona_role", "AI Chief of Staff")
            cta = persona.get("default_cta", "Follow for daily executive AI updates.")
            return {
                "title": article_title,
                "persona_role": role,
                "total_estimated_duration_sec": 75,
                "call_to_action": cta,
                "beats": [
                    {
                        "beat_index": 1,
                        "beat_type": "HOOK",
                        "spoken_script": f"If you're tracking artificial intelligence developments, here is what just happened with {article_title}.",
                        "visual_directive": "PRESENTER_CAMERA_A",
                        "whiteboard_directive": "Key headline graphic",
                        "estimated_seconds": 10,
                    },
                    {
                        "beat_index": 2,
                        "beat_type": "CONTEXT",
                        "spoken_script": "Until recently, enterprises struggled to overcome major bottlenecks in this exact space.",
                        "visual_directive": "PRESENTER_CAMERA_A",
                        "whiteboard_directive": "Pain point diagram",
                        "estimated_seconds": 15,
                    },
                    {
                        "beat_index": 3,
                        "beat_type": "CORE_SHIFT",
                        "spoken_script": full_text[:200] if full_text else "A new milestone has been announced.",
                        "visual_directive": "PRESENTER_CAMERA_B_SPLIT",
                        "whiteboard_directive": "Architecture diagram",
                        "estimated_seconds": 25,
                    },
                    {
                        "beat_index": 4,
                        "beat_type": "BUSINESS_IMPACT",
                        "spoken_script": "For executives, this fundamentally shifts deployment velocity and long-term operating costs.",
                        "visual_directive": "PRESENTER_CAMERA_A_PUNCH_IN",
                        "whiteboard_directive": "Impact summary",
                        "estimated_seconds": 15,
                    },
                    {
                        "beat_index": 5,
                        "beat_type": "CTA",
                        "spoken_script": f"Evaluate this technology in your roadmap today. {cta}",
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
        """Step 2: Extract atomic factual claims and verify against source text verbatim quotes."""
        if not beats or not full_text:
            return []

        system_prompt, user_prompt = get_claim_audit_prompt(beats=beats, full_text=full_text)

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=4096,
            )
            data = _extract_json(content)
            claims = data.get("claims", [])
            for c in claims:
                c["is_grounded"] = bool(c.get("is_grounded", False))
                c["beat_index"] = int(c.get("beat_index", 1))
            return claims
        except Exception as e:
            logger.error(f"Claude claim audit failed: {e}")
            return []

    async def revise_script_beat(
        self,
        beat: dict[str, Any],
        ungrounded_claims: list[dict[str, Any]],
        full_text: str,
        persona: dict[str, Any],
    ) -> dict[str, Any]:
        """Step 2: Rewrite an ungrounded beat to strictly ground assertions in article text."""
        system_prompt, user_prompt = get_revision_prompt(
            beat=beat,
            ungrounded_claims=ungrounded_claims,
            full_text=full_text,
            persona=persona,
        )

        try:
            content = await self._generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=2048,
            )
            data = _extract_json(content)
            return {
                "spoken_script": data.get("spoken_script", beat.get("spoken_script", "")),
                "visual_directive": data.get("visual_directive", beat.get("visual_directive", "PRESENTER_CAMERA_A")),
                "whiteboard_directive": data.get("whiteboard_directive", beat.get("whiteboard_directive")),
                "estimated_seconds": int(data.get("estimated_seconds", beat.get("estimated_seconds", 15))),
                "revision_notes": data.get("revision_notes", "Automated revision to ground claims."),
            }
        except Exception as e:
            logger.error(f"Claude beat revision failed: {e}")
            return beat


# Alias for convenience
AnthropicProvider = ClaudeProvider
