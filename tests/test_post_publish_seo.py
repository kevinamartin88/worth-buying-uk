from __future__ import annotations

from unittest.mock import Mock

from post_publish_seo import PageSignals, public_url, same_site, sitemap_contains


def test_manual_review_summary_filters_urls_and_makes_no_submission(monkeypatch, tmp_path):
    import post_publish_seo as seo
    p = tmp_path / 'summary.txt'
    p.write_text('Earlier steps\n', encoding='utf-8')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(p))
    url = 'https://www.worthbuyinguk.co.uk/2026/10/guide.html'
    seo.manual_indexing_summary('uk', [url, url, 'https://evil.example/guide'])
    result = p.read_text(encoding='utf-8')
    assert result.startswith('Earlier steps')
    assert result.count('<li>') == 1
    assert 'evil.example' not in result
    assert 'has not requested indexing' in result


def test_summary_failure_does_not_block_publishing(monkeypatch):
    import post_publish_seo as seo
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', 'unused')
    monkeypatch.setattr(seo, 'get_site_host', lambda market: 'www.worthbuyinguk.co.uk')
    def fail(*args, **kwargs):
        raise PermissionError('Test-only write failure')
    monkeypatch.setattr(seo.Path, 'open', fail)
    seo.manual_indexing_summary('uk', ['https://www.worthbuyinguk.co.uk/2026/10/guide.html'])


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

