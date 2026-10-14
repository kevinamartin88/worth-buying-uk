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


def test_sitemap_is_fetched_once_for_a_batch():
    session = Mock()
    session.get.return_value.content = b'<urlset><url><loc>https://example.com/a</loc></url></urlset>'
    cache = {}
    assert sitemap_contains(session, 'https://example.com/sitemap.xml', 'https://example.com/a', 'example.com', cache=cache)
    assert not sitemap_contains(session, 'https://example.com/sitemap.xml', 'https://example.com/b', 'example.com', cache=cache)
    assert session.get.call_count == 1


def test_missing_credentials_are_unconfirmed_not_submitted(monkeypatch):
    import post_publish_seo as seo
    monkeypatch.delenv('GSC_WRITE_REFRESH_TOKEN', raising=False)
    monkeypatch.setattr(seo, 'configured', lambda: False)
    checkpoint = Mock()
    report = seo.search_console('uk', ['https://www.worthbuyinguk.co.uk/a'], ['https://www.worthbuyinguk.co.uk/sitemap.xml'], checkpoint)
    assert report['sitemaps'][0]['state'] == 'unavailable'
    assert report['inspections']['https://www.worthbuyinguk.co.uk/a']['state'] == 'unconfirmed'
    assert checkpoint.call_count >= 2


def test_partial_submission_and_inspection_failures_are_recorded_independently(monkeypatch):
    import post_publish_seo as seo
    for key in ['GSC_WRITE_REFRESH_TOKEN', 'GSC_WRITE_CLIENT_ID', 'GSC_WRITE_CLIENT_SECRET']:
        monkeypatch.setenv(key, 'test-only')
    monkeypatch.setattr(seo, 'Credentials', Mock())
    writer = Mock()
    writer.sitemaps().submit().execute.side_effect = [RuntimeError('temporary'), {}]
    reader = Mock()
    reader.urlInspection().index().inspect().execute.side_effect = [
        {'inspectionResult': {'indexStatusResult': {'verdict': 'PASS', 'coverageState': 'Submitted and indexed'}}},
        RuntimeError('temporary')]
    monkeypatch.setattr(seo, 'build', lambda *args, **kwargs: writer)
    monkeypatch.setattr(seo, 'configured', lambda: True)
    monkeypatch.setattr(seo, 'build_service', lambda: reader)
    monkeypatch.setattr(seo, 'choose_site', lambda *args: 'sc-domain:worthbuyinguk.co.uk')
    urls = ['https://www.worthbuyinguk.co.uk/a', 'https://www.worthbuyinguk.co.uk/b']
    result = seo.search_console('uk', urls, ['https://www.worthbuyinguk.co.uk/sitemap.xml',
                                         'https://www.worthbuyinguk.co.uk/sitemap-pages.xml'])
    assert [row['state'] for row in result['sitemaps']] == ['failed', 'submitted']
    assert result['inspections'][urls[0]]['state'] == 'indexed'
    assert result['inspections'][urls[1]]['state'] == 'unconfirmed'
    assert writer.sitemaps().submit().execute.call_count == 2
    assert reader.urlInspection().index().inspect().execute.call_count == 2
    assert reader.urlInspection().index().inspect().execute.call_args.kwargs == {'num_retries': 2}


def test_daily_follow_up_selects_recent_unique_public_urls(monkeypatch, tmp_path):
    import json
    import post_publish_seo as seo
    (tmp_path / 'state').mkdir()
    rows = {
        'old': {'status': 'published', 'url': 'https://www.worthbuyinguk.co.uk/old', 'daily_featured_date': '2026-10-01'},
        'new': {'status': 'published', 'url': 'https://www.worthbuyinguk.co.uk/new', 'daily_featured_date': '2026-10-14'},
        'duplicate': {'status': 'published', 'url': 'https://www.worthbuyinguk.co.uk/new', 'daily_featured_date': '2026-10-13'},
        'draft': {'status': 'draft', 'url': 'https://www.worthbuyinguk.co.uk/draft', 'daily_featured_date': '2026-10-15'},
        'outside': {'status': 'published', 'url': 'https://other.example/other', 'daily_featured_date': '2026-10-16'},
        'legacy': {'status': 'published', 'url': 'https://www.worthbuyinguk.co.uk/legacy', 'source_sha': 'ffffffffffffffffffff'},
    }
    (tmp_path / 'state/articles_published.json').write_text(json.dumps(rows), encoding='utf-8')
    monkeypatch.setattr(seo, 'ROOT', tmp_path)
    selected = seo.recent_posts('uk', 2)
    assert [x['url'] for x in selected] == ['https://www.worthbuyinguk.co.uk/new', 'https://www.worthbuyinguk.co.uk/old']


def test_google_submission_precedes_failed_public_fetch_and_report_is_saved(monkeypatch, tmp_path):
    import json
    import requests
    import post_publish_seo as seo
    url = 'https://www.worthbuyinguk.co.uk/guide'
    monkeypatch.setattr(seo, 'changed_posts', lambda market: [{'url': url}])
    order = []
    def console(market, urls, feeds, checkpoint):
        order.append('google')
        result = {'property': 'sc-domain:worthbuyinguk.co.uk',
                  'sitemaps': [{'url': feed, 'state': 'submitted'} for feed in feeds],
                  'inspections': {url: {'state': 'not_indexed', 'coverage': 'Discovered – currently not indexed'}}}
        checkpoint(result)
        return result
    monkeypatch.setattr(seo, 'search_console', console)
    def failure(*args, **kwargs):
        order.append('public')
        raise requests.Timeout('test-only')
    monkeypatch.setattr(seo, 'sitemap_contains', failure)
    monkeypatch.setattr(seo, 'inspect_page', failure)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    path = tmp_path / 'report.json'
    report = seo.run('uk', report_path=path)
    assert order[0] == 'google'
    assert report['complete'] is True and report['attention_required'] is True
    assert report['google']['sitemaps'][0]['state'] == 'submitted'
    assert report['individual_indexing_requests_submitted'] is False
    assert json.loads(path.read_text(encoding='utf-8'))['public_checks'][url]['page_check_error'] == 'Timeout'


def test_summary_classifies_manual_actions_without_claiming_requests(monkeypatch, tmp_path):
    from src.google_discovery_report import inspection_record, new_report, next_action, write_summary
    url = 'https://www.worthbuyinguk.co.uk/guide'
    assert inspection_record({})['state'] == 'unconfirmed'
    indexed = inspection_record({'verdict': 'PASS', 'googleCanonical': url})
    assert next_action(url, indexed).startswith('Already indexed')
    assert 'canonical' in next_action(url, {**indexed, 'google_canonical': url + '-other'})
    assert 'block' in next_action(url, {'state': 'not_indexed', 'indexing_state': 'BLOCKED_BY_META_TAG'})
    target = tmp_path / 'summary.txt'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(target))
    report = new_report('uk', [url], 'after-publication')
    report['google']['inspections'][url] = indexed
    write_summary(report)
    text = target.read_text(encoding='utf-8')
    assert 'Individual indexing requests submitted by this workflow: **No**' in text
    assert 'Already indexed' in text
    assert 'Report complete: **False**' in text


def test_report_and_summary_write_errors_do_not_raise(monkeypatch):
    from pathlib import Path
    from src.google_discovery_report import new_report, save_report, write_summary
    report = new_report('uk', [], 'after-publication')
    def fail(*args, **kwargs):
        raise PermissionError('test-only')
    monkeypatch.setattr(Path, 'mkdir', fail)
    save_report(Path('unused/report.json'), report)
    monkeypatch.setattr(Path, 'open', fail)
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', 'unused-summary')
    write_summary(report)


