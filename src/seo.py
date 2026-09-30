from __future__ import annotations

import html
import re


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def plain_text(value: str) -> str:
    """Return compact readable text from a small HTML fragment."""
    return _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()


def meta_description(title: str, content_html: str, market: str, limit: int = 155) -> str:
    """Build a useful description for feeds and Blogger's Search Description field."""
    title_text = plain_text(title).rstrip(" .:-")
    country = "UK" if market == "EBAY_GB" else "US"
    candidate = f"{title_text}: a current {country} shortlist with price, seller-quality and buying checks."
    if len(candidate) <= limit:
        return candidate
    fallback = plain_text(content_html)[: limit + 1]
    if len(fallback) <= limit:
        return fallback
    cut = fallback.rfind(" ", 0, limit - 1)
    return fallback[:cut].rstrip(" ,.;:") + "…"


def audit_post(content_html: str) -> list[str]:
    """Return blocking SEO/editorial defects in generated post HTML."""
    problems: list[str] = []
    lowered = content_html.lower()
    if 'rel="sponsored nofollow"' not in lowered:
        problems.append("affiliate links are not qualified as sponsored nofollow")
    if re.search(r'alt=["\'](?:image|photo|picture|)["\']', content_html, re.I):
        problems.append("generic or empty image alt text")
    if "<h2" not in lowered or "<h3" not in lowered:
        problems.append("incomplete heading hierarchy")
    if len(plain_text(content_html).split()) < 250:
        problems.append("insufficient useful copy")
    return problems
