import re
from typing import Any
from urllib.parse import quote_plus, urlparse
import feedparser
import httpx
from app.core.cipher import validate_outbound_url
from app.core.log import logger
from app.services.ingestion.rss_fetcher import MODERN_BROWSER_HEADERS
from app.services.llm.base import LLMProviderAdapter

COMMON_STOP_WORDS = {
    "with", "this", "that", "from", "have", "more", "what", "when", "where",
    "your", "their", "about", "into", "over", "after", "will", "been", "says",
    "here", "then", "some", "news", "report", "first", "could", "would",
    "just", "make", "take", "using", "uses", "amid", "back", "next",
}

DISALLOWED_DOMAINS = {
    "youtube.com", "youtu.be", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "reddit.com", "wikipedia.org", "linkedin.com", "tiktok.com", "duckduckgo.com"
}


def extract_root_domain(url: str) -> str:
    """Extract registered root domain (e.g. techcrunch.com) from a URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        host = netloc.split(":")[0]
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return ""


def is_domain_independent(url_a: str, url_b: str) -> bool:
    """Return True if both URLs originate from distinct root domains."""
    dom_a = extract_root_domain(url_a)
    dom_b = extract_root_domain(url_b)
    if not dom_a or not dom_b:
        return False
    return dom_a != dom_b


def extract_title_keywords(title: str) -> set[str]:
    """Extract normalized significant alphanumeric keywords from an article headline."""
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower())
    return {w for w in words if w not in COMMON_STOP_WORDS}


def cluster_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group articles covering the same breaking event into a single cluster.

    Attaches corroborating candidate items from distinct root domains to the lead
    article's `cluster_secondaries` list. Returns deduplicated lead candidates.
    """
    clusters: list[dict[str, Any]] = []
    for cand in candidates:
        cand_words = extract_title_keywords(cand.get("title", ""))
        cand_url = cand.get("url", "")
        matched_lead: dict[str, Any] | None = None

        for lead in clusters:
            lead_url = lead.get("url", "")
            if not is_domain_independent(cand_url, lead_url):
                continue
            lead_words = extract_title_keywords(lead.get("title", ""))
            overlap = cand_words.intersection(lead_words)
            if len(overlap) >= 3:
                matched_lead = lead
                break

        if matched_lead:
            if "cluster_secondaries" not in matched_lead:
                matched_lead["cluster_secondaries"] = []
            matched_lead["cluster_secondaries"].append(cand)
        else:
            cand_lead = dict(cand)
            cand_lead["cluster_secondaries"] = []
            clusters.append(cand_lead)

    return clusters


def find_secondary_candidate(
    primary_article: dict[str, Any], pool: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Search for a candidate covering the same topic from an independent root domain."""
    # 1. First check if a pre-grouped cluster secondary already exists
    cluster_secondaries = primary_article.get("cluster_secondaries")
    if cluster_secondaries:
        for sec in cluster_secondaries:
            if is_domain_independent(primary_article.get("url", ""), sec.get("url", "")):
                return sec

    # 2. Search broader candidate pool for semantic keyword overlap
    prim_url = primary_article.get("url", "")
    prim_words = extract_title_keywords(primary_article.get("title", ""))

    best_match: dict[str, Any] | None = None
    best_overlap = 0

    for candidate in pool:
        cand_url = candidate.get("url", "")
        if not is_domain_independent(prim_url, cand_url):
            continue

        cand_words = extract_title_keywords(candidate.get("title", ""))
        overlap = len(prim_words.intersection(cand_words))

        if overlap >= 2 and overlap > best_overlap:
            best_overlap = overlap
            best_match = candidate

    return best_match


async def search_external_secondary_source(
    primary_title: str, primary_url: str
) -> dict[str, Any] | None:
    """Active web search fallback when no corroborating source exists in the local RSS batch.

    Queries journalistic news search to locate an independent article on the same story.
    """
    clean_title = re.sub(r"[:|–—-].*", "", primary_title).strip()
    if len(clean_title) < 15:
        clean_title = primary_title[:80].strip()

    search_query = quote_plus(clean_title)
    search_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(search_url, headers=MODERN_BROWSER_HEADERS)
            if resp.status_code != 200:
                return None
            feed = feedparser.parse(resp.text)

            for entry in feed.entries[:8]:
                raw_link = entry.get("link", "").strip()
                entry_title = entry.get("title", "").strip()
                source_meta = entry.get("source", {})
                source_name = source_meta.get("title", "") if isinstance(source_meta, dict) else ""

                if not raw_link or not entry_title:
                    continue

                # Check root-domain independence
                if source_name and extract_root_domain(primary_url) in source_name.lower():
                    continue

                summary = entry.get("summary", "")
                if summary and ("<" in summary and ">" in summary):
                    summary = re.sub(r"<[^>]+>", " ", summary).strip()

                return {
                    "id": None,
                    "url": raw_link,
                    "title": entry_title,
                    "summary": summary or f"Corroborating coverage reported by {source_name or 'independent press'}.",
                    "is_external": True,
                    "source_name": source_name or "Independent Web News",
                }
    except Exception as e:
        logger.warning(f"External secondary search failed for '{primary_title[:40]}': {e}")
        return None
    return None


async def verify_article_corroboration(
    primary_article: dict[str, Any],
    secondary_article: dict[str, Any] | None,
    primary_text: str,
    secondary_text: str,
    llm_provider: LLMProviderAdapter,
) -> dict[str, Any]:
    """Execute dual-source corroboration check against factual agreement threshold (>= 0.75)."""
    if not secondary_article or not secondary_text:
        return {
            "agreement_score": 0.50,
            "is_verified": False,
            "corroboration_notes": "Single-source report; no independent secondary domain corroboration found.",
            "secondary_url": None,
            "secondary_source": None,
        }

    # Verify domain independence
    if not is_domain_independent(primary_article.get("url", ""), secondary_article.get("url", "")):
        return {
            "agreement_score": 0.0,
            "is_verified": False,
            "corroboration_notes": "Secondary source violates root-domain independence requirement.",
            "secondary_url": secondary_article.get("url"),
            "secondary_source": extract_root_domain(secondary_article.get("url", "")),
        }

    result = await llm_provider.verify_corroboration(
        primary_title=primary_article.get("title", ""),
        primary_text=primary_text,
        secondary_title=secondary_article.get("title", ""),
        secondary_text=secondary_text,
    )

    result["secondary_url"] = secondary_article.get("url")
    result["secondary_source"] = secondary_article.get("source_name") or extract_root_domain(secondary_article.get("url", ""))

    logger.info(
        f"Verification for '{primary_article.get('title')}': "
        f"Agreement={result.get('agreement_score')}, Verified={result.get('is_verified')} "
        f"(Source: {result['secondary_source']})"
    )
    return result
