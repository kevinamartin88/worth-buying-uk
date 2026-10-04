from __future__ import annotations

import html
from urllib.parse import parse_qs, urlsplit

from publish_articles import add_uk_epn_tracking
from publish_articles_us import add_us_epn_tracking


def _href(rendered: str) -> str:
    start = rendered.index('href="') + len('href="')
    end = rendered.index('"', start)
    return html.unescape(rendered[start:end])


def test_uk_ebay_links_keep_article_level_custom_id():
    content = '<a href="https://www.ebay.co.uk/itm/123?foo=bar&customid=old">View</a>'
    rendered = add_uk_epn_tracking(content, custom_id="best-air-fryers-worth-buying-uk-2026")
    query = parse_qs(urlsplit(_href(rendered)).query)
    assert query["campid"] == ["5339209132"]
    assert query["customid"] == ["best-air-fryers-worth-buying-uk-2026"]


def test_us_ebay_links_keep_article_level_custom_id():
    content = '<a href="https://www.ebay.com/itm/123?foo=bar&customid=old">View</a>'
    rendered = add_us_epn_tracking(content, custom_id="best-ssds-worth-buying-us-2026")
    query = parse_qs(urlsplit(_href(rendered)).query)
    assert query["campid"] == ["5339209205"]
    assert query["customid"] == ["best-ssds-worth-buying-us-2026"]


def test_custom_id_is_capped_at_epn_limit():
    long_id = "a" * 400
    content = '<a href="https://www.ebay.co.uk/itm/123">View</a>'
    rendered = add_uk_epn_tracking(content, custom_id=long_id)
    query = parse_qs(urlsplit(_href(rendered)).query)
    assert len(query["customid"][0]) == 256
