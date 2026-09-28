from __future__ import annotations

from unittest.mock import Mock

from post_publish_seo import PageSignals, public_url, same_site, sitemap_contains


def test_page_signals_find_canonical_and_validate_json_ld():
    parser = PageSignals()
    parser.feed('<link rel="canonical" href="https://example.com/post">'
                '<script type="application/ld+json">{"@type":"Article"}</script>')
    assert parser.canonical == "https://example.com/post"
    assert parser.json_ld == ['{"@type":"Article"}']


def test_sitemap_checks_only_same_site_children():
    response = Mock()
    response.content = (b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                        b'<sitemap><loc>https://example.com/posts.xml</loc></sitemap>'
                        b'<sitemap><loc>https://evil.example/posts.xml</loc></sitemap>'
                        b'</sitemapindex>')
    response.raise_for_status.return_value = None
    child = Mock()
    child.content = (b'<urlset><url><loc>https://example.com/post</loc></url></urlset>')
    child.raise_for_status.return_value = None
    session = Mock()
    session.get.side_effect = [response, child]
    assert sitemap_contains(session, "https://example.com/sitemap.xml", "https://example.com/post", "example.com")
    assert session.get.call_count == 2
    assert not same_site("https://example.com.evil.test/post", "example.com")


def test_blogger_url_maps_to_active_public_domain():
    assert public_url("https://worthbuyinguk.blogspot.com/2026/09/post.html", "uk") == (
        "https://www.worthbuyinguk.co.uk/2026/09/post.html"
    )
    assert public_url("https://other.blogspot.com/post.html", "uk") is None
