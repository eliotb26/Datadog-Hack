"""
Fetch a company website URL and extract main text for brand intake.
Uses httpx + simple HTML parsing (no JS rendering). Best for static marketing pages.
"""
import re
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Max chars of body text to pass to the agent (avoid token overflow)
MAX_BODY_CHARS = 12_000
# Request timeout
FETCH_TIMEOUT = 15.0
# User-Agent so we get desktop HTML
USER_AGENT = "Mozilla/5.0 (compatible; SIGNAL-Bot/1.0; +https://signal.example.com)"


def _normalize_url(url: str) -> str:
    """Ensure URL has a scheme."""
    url = url.strip()
    if not url:
        return url
    if not re.match(r"^https?://", url, re.I):
        return "https://" + url
    return url


def _extract_text_from_html(html: str) -> tuple[str, str, str]:
    """
    Extract title, meta description, and main body text from HTML.
    Returns (title, meta_description, body_text).
    """
    title = ""
    meta_desc = ""
    # Title
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()

    # Meta description
    m = re.search(
        r'<meta\s+[^>]*name\s*=\s*["\']description["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            r'<meta\s+[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*name\s*=\s*["\']description["\']',
            html,
            re.I,
        )
    if m:
        meta_desc = re.sub(r"\s+", " ", m.group(1)).strip()

    # Remove script/style and get body text
    cleaned = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    cleaned = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<nav[^>]*>[\s\S]*?</nav>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<footer[^>]*>[\s\S]*?</footer>", " ", cleaned, flags=re.I)
    # Strip all tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode common entities
    cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    body = cleaned[:MAX_BODY_CHARS] if len(cleaned) > MAX_BODY_CHARS else cleaned

    return title, meta_desc, body


async def fetch_website_text(url: str) -> Optional[str]:
    """
    Fetch a URL and return a single text block suitable for the brand intake agent:
    title, meta description, and main body text.

    Returns None on fetch or parse errors (logged).
    """
    url = _normalize_url(url)
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            logger.warning("website_fetch invalid url: %s", url)
            return None
    except Exception as e:
        logger.warning("website_fetch url parse error: %s", e)
        return None

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        logger.warning("website_fetch HTTP error for %s: %s", url, e)
        return None
    except Exception as e:
        logger.warning("website_fetch error for %s: %s", url, e)
        return None

    try:
        title, meta_desc, body = _extract_text_from_html(html)
        parts = []
        if title:
            parts.append(f"Page title: {title}")
        if meta_desc:
            parts.append(f"Meta description: {meta_desc}")
        if body:
            parts.append(f"Main content:\n{body}")
        if not parts:
            logger.warning("website_fetch no text extracted from %s", url)
            return None
        return "\n\n".join(parts)
    except Exception as e:
        logger.warning("website_fetch extract error for %s: %s", url, e)
        return None
