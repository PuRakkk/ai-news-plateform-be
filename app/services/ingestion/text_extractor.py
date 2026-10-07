import re
from html import unescape
import httpx
from app.core.cipher import validate_outbound_url
from app.core.log import logger
from app.services.ingestion.rss_fetcher import MODERN_BROWSER_HEADERS

BROWSER_HEADERS = MODERN_BROWSER_HEADERS


def clean_html_to_text(html_content: str) -> str:
    """Strip HTML markup, scripts, and navigation to produce clean readable text."""
    # Remove script, style, head, nav, footer, form, noscript blocks
    cleaned = re.sub(
        r"<(script|style|head|nav|footer|header|aside|form|noscript)[^>]*>.*?</\1>",
        " ",
        html_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove HTML comments
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    # Replace block tags with newlines
    cleaned = re.sub(r"<(p|div|h[1-6]|li|tr|br)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    # Strip all remaining tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode HTML entities (&amp;, &nbsp;, etc.)
    text = unescape(cleaned)
    # Collapse excess whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)


async def extract_article_text(url: str, max_chars: int = 5000) -> str:
    """Safely fetch and extract clean article text with SSRF protection."""
    if not validate_outbound_url(url):
        logger.warning(f"SSRF validation failed for URL: {url}")
        return ""

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=BROWSER_HEADERS)
            resp.raise_for_status()
            text = clean_html_to_text(resp.text)
            return text[:max_chars]
    except Exception as e:
        logger.warning(f"Failed to extract full text from {url}: {e}")
        return ""
