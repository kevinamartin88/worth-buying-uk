from __future__ import annotations

import re


_DISCLOSURE_PARAGRAPH = re.compile(
    r"<p\b[^>]*>(?:(?!</p>).)*?(?:affiliate(?:\s+disclosure)?|"
    r"earn\s+(?:a\s+)?commission|receive\s+commission)(?:(?!</p>).)*?</p>\s*",
    re.IGNORECASE | re.DOTALL,
)


def clean_article_disclosures(content_html: str) -> str:
    """Remove repeated per-article disclosures; the sites carry a global disclosure."""
    return _DISCLOSURE_PARAGRAPH.sub("", content_html)
