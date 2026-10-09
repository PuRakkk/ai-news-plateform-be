import asyncio
import hashlib
import re
import time
import zoneinfo
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin
import feedparser
import httpx
from app.core.config import settings
from app.core.log import logger

MODERN_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "Upgrade-Insecure-Requests": "1",
}
USER_AGENT = MODERN_BROWSER_HEADERS["User-Agent"]


def compute_article_hash(url: str, title: str) -> str:
    """Generate deterministic SHA-256 hash for deduplication."""
    normalized = f"{url.strip().lower()}:{title.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_yesterday_cutoff(tz_name: str | None = None) -> datetime:
    """Calculate the UTC datetime representing the start of yesterday (00:00:00) in local timezone."""
    tz_str = tz_name or settings.APP_TIMEZONE
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
    now_local = datetime.now(tz)
    yesterday = now_local.date() - timedelta(days=1)
    start_of_yesterday = datetime.combine(yesterday, dtime.min, tzinfo=tz)
    return start_of_yesterday.astimezone(timezone.utc)


def is_published_today(dt: datetime | None, tz_name: str | None = None) -> bool:
    """Check if the given datetime corresponds to today in the local timezone."""
    if not dt:
        return False
    tz_str = tz_name or settings.APP_TIMEZONE
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
    dt_local = dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=timezone.utc).astimezone(tz)
    now_local = datetime.now(tz)
    return dt_local.date() == now_local.date()


def find_rss_autodiscovery_link(html_text: str, base_url: str) -> str | None:
    """Scan HTML head for RSS or Atom autodiscovery link tags."""
    head_match = re.search(r"<head[^>]*>(.*?)</head>", html_text, re.DOTALL | re.IGNORECASE)
    search_space = head_match.group(1) if head_match else html_text[:6000]

    link_matches = re.findall(r"<link[^>]+>", search_space, re.IGNORECASE)
    for tag in link_matches:
        tag_lower = tag.lower()
        if "alternate" in tag_lower and any(
            t in tag_lower for t in ["application/rss+xml", "application/atom+xml", "text/xml"]
        ):
            href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if href_m:
                return urljoin(base_url, href_m.group(1))
    return None


async def fetch_rss_feed(
    feed_url: str,
    max_entries: int | None = None,
    max_age_days: int | None = None,
    only_yesterday_and_today: bool | None = None,
) -> list[dict[str, Any]]:
    """Download and parse an RSS feed with freshness and per-feed limits."""
    limit = max_entries or settings.RSS_MAX_ENTRIES_PER_FEED

    use_yesterday_today = (
        only_yesterday_and_today
        if only_yesterday_and_today is not None
        else settings.RSS_ONLY_YESTERDAY_AND_TODAY
    )

    if use_yesterday_today:
        cutoff = compute_yesterday_cutoff()
    else:
        age_days = max_age_days or settings.RSS_MAX_AGE_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=age_days)

    raw_xml: str | None = None
    parsed = None

    logger.info(f"Connecting to RSS feed '{feed_url}'...")

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=MODERN_BROWSER_HEADERS) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "").lower()
            resp_text = resp.text

            # Detect whether the response is an HTML webpage rather than RSS/Atom XML
            is_html = (
                "text/html" in content_type
                or resp_text[:400].strip().lower().startswith("<!doctype html")
                or resp_text[:400].strip().lower().startswith("<html")
            )

            if is_html:
                logger.info(f"URL '{feed_url}' returned HTML. Checking for RSS autodiscovery <link>...")
                discovered_url = find_rss_autodiscovery_link(resp_text, str(resp.url))

                if discovered_url and discovered_url != feed_url:
                    logger.info(f"Discovered RSS feed '{discovered_url}' in HTML head. Fetching discovered feed...")
                    feed_resp = await client.get(discovered_url)
                    feed_resp.raise_for_status()
                    raw_xml = feed_resp.text
                else:
                    logger.warning(
                        f"URL '{feed_url}' returned an HTML webpage (Content-Type: '{content_type}'), not an XML/RSS feed. "
                        f"feedparser cannot extract RSS items from an HTML webpage. Please configure a valid RSS endpoint (e.g. /feed or .xml)."
                    )
                    return []
            else:
                raw_xml = resp_text

    except Exception as e:
        logger.warning(
            f"HTTP fetch failed for RSS feed '{feed_url}': {e}. "
            f"Attempting fallback via direct feedparser (with 15s timeout)..."
        )
        try:
            logger.info(f"[Fallback] Direct feedparser connecting to '{feed_url}'...")
            parsed = await asyncio.wait_for(
                asyncio.to_thread(feedparser.parse, feed_url),
                timeout=15.0,
            )
            entries_count = len(parsed.entries) if parsed and hasattr(parsed, "entries") else 0
            bozo_status = getattr(parsed, "bozo", False)
            http_status = getattr(parsed, "status", "N/A")
            logger.info(
                f"[Fallback] Direct feedparser completed for '{feed_url}': "
                f"HTTP status={http_status}, entries_found={entries_count}, bozo={bozo_status}"
            )
        except asyncio.TimeoutError:
            logger.error(f"[Fallback] Direct feedparser timed out after 15s for '{feed_url}'. Skipping feed.")
            return []
        except Exception as parse_err:
            logger.error(f"[Fallback] Direct feedparser encountered an error for '{feed_url}': {parse_err}")
            return []

    # If raw_xml was retrieved via httpx, parse it in a worker thread to keep the event loop responsive
    if parsed is None:
        if not raw_xml:
            logger.error(f"No XML payload retrieved for feed '{feed_url}'.")
            return []
        parsed = await asyncio.to_thread(feedparser.parse, raw_xml)

    if parsed.bozo and not parsed.entries:
        logger.error(f"Failed to parse RSS feed from '{feed_url}': {parsed.bozo_exception}")
        return []

    articles: list[dict[str, Any]] = []
    # Cap entries per feed to avoid reading massive unpaginated archives
    for idx, entry in enumerate(parsed.entries[:limit]):
        url = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not url or not title:
            continue

        published_dt: datetime | None = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_dt = datetime.fromtimestamp(
                    time.mktime(entry.published_parsed), tz=timezone.utc
                )
            except Exception:
                published_dt = None

        # Filter out stale articles older than cutoff window
        if published_dt and published_dt < cutoff:
            continue

        summary = entry.get("summary", entry.get("description", ""))
        # Clean HTML tags from summary if needed
        if summary and ("<" in summary and ">" in summary):
            import re
            summary = re.sub(r"<[^>]+>", " ", summary).strip()

        # Filter out non-news content (podcasts, audio teasers, sponsored promos)
        noise_check = f"{title.lower()} {(summary or '').lower()}"
        if any(noise in noise_check for noise in ["podcast", "on equity, we discussed", "listen on apple", "listen on spotify", "sponsored post"]):
            continue

        content_hash = compute_article_hash(url, title)

        articles.append(
            {
                "url": url,
                "title": title,
                "summary": summary[:1000] if summary else None,
                "content_hash": content_hash,
                "published_at": published_dt,
            }
        )

    cutoff_desc = (
        f"yesterday & today (since {cutoff.strftime('%Y-%m-%d %H:%M UTC')})"
        if use_yesterday_today
        else f"since {cutoff.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    logger.info(f"Ingested {len(articles)} fresh entries ({cutoff_desc}) from RSS feed: {feed_url}")
    return articles
