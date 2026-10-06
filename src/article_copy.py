from __future__ import annotations

import re

DISCLOSURE = (
    '<p class="wb-affiliate-disclosure"><strong>Affiliate links:</strong> '
    'Some retailer links may earn Worth Buying a commission at no extra cost to you.</p>\n'
)
_PARAGRAPH = re.compile(r"<p\b[^>]*>.*?</p>\s*", re.IGNORECASE | re.DOTALL)


def _insert_disclosure_after_intro(content_html: str) -> str:
    """Keep disclosure clear, but out of the homepage/article opening excerpt."""
    targets = (
        '<section class="wb-usa-buying-cards"',
        "<h2>Best current options at a glance</h2>",
        "<h2>Current picks worth comparing</h2>",
        "<h2>Current retailer searches worth checking</h2>",
    )
    for target in targets:
        index = content_html.find(target)
        if index >= 0:
            return content_html[:index] + DISCLOSURE + content_html[index:]

    # Generic/manual articles: place it before the first substantive heading so
    # the first paragraph remains reader-focused while disclosure still appears
    # before the main commercial body.
    heading = re.search(r"<h[23]\b", content_html, re.IGNORECASE)
    if heading:
        index = heading.start()
        return content_html[:index] + DISCLOSURE + content_html[index:]

    return content_html.rstrip() + "\n" + DISCLOSURE


def clean_article_disclosures(content_html: str) -> str:
    """Keep one concise disclosure without leading the page or homepage excerpt."""
    def remove_duplicate(match: re.Match) -> str:
        paragraph = match.group(0)
        text = re.sub(r"<[^>]+>", "", paragraph).strip().casefold()
        if "wb-affiliate-disclosure" in paragraph or text.startswith((
            "affiliate disclosure:",
            "affiliate links:",
            "some links in this article are affiliate links",
            "some links may be affiliate links",
            "this page contains affiliate links",
        )):
            return ""
        return paragraph

    cleaned = _PARAGRAPH.sub(remove_duplicate, content_html).strip()
    if "<!-- wb-savvy-disclosure: footer -->" in content_html:
        return cleaned + "\n" + DISCLOSURE
    return _insert_disclosure_after_intro(cleaned)
