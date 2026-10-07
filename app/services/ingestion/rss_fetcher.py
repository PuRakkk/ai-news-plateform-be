import hashlib
import time
import zoneinfo
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any
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

    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers=headers)
            resp.raise_for_status()
            raw_xml = resp.text
    except Exception as e:
        logger.warning(f"HTTP fetch failed for RSS feed {feed_url}: {e}. Trying direct feedparser.")
        raw_xml = feed_url

    parsed = feedparser.parse(raw_xml)
    if parsed.bozo and not parsed.entries:
        logger.error(f"Failed to parse RSS feed from {feed_url}: {parsed.bozo_exception}")
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
