from __future__ import annotations

import re

DISCLOSURE = (
    '<p class="wb-affiliate-disclosure"><strong>Affiliate disclosure:</strong> '
    'If you buy through our retailer links, Worth Buying may earn a commission '
    'at no extra cost to you.</p>\n'
)
_PARAGRAPH = re.compile(r"<p\b[^>]*>.*?</p>\s*", re.IGNORECASE | re.DOTALL)


def clean_article_disclosures(content_html: str) -> str:
    """Keep one clear disclosure at the top without deleting editorial copy."""
    def remove_duplicate(match: re.Match) -> str:
        paragraph = match.group(0)
        text = re.sub(r"<[^>]+>", "", paragraph).strip().casefold()
        if "wb-affiliate-disclosure" in paragraph or text.startswith((
            "affiliate disclosure:", "some links in this article are affiliate links",
            "this page contains affiliate links",
        )):
            return ""
        return paragraph

    return DISCLOSURE + _PARAGRAPH.sub(remove_duplicate, content_html).lstrip()
