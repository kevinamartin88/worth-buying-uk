import copy
import html
from urllib.parse import parse_qs, urlsplit

import pytest

from src.publication_quality import choose_description, repair_affiliate_links, affiliate_issues, CONFIG
from src.publishing_seo import repair_metadata, enrich_metadata, metadata_html
from verify_publication import assess, verify_one


def article(market='uk'):
    return {'slug': 'coffee-guide', 'title': 'Best Coffee Machines Worth Buying in the UK (2026)' if market == 'uk' else 'Best Coffee Makers Worth Buying in the USA (2026)',
            'content_html': '<h2>Coffee makers</h2><p>Filter vs espresso, milk drinks, cleaning, warranty and retailer comparisons.</p>',
            '_seo': {'description': f'Compare coffee {"machines in the UK" if market == "uk" else "makers in the USA"}: filter vs espresso, milk drinks, cleaning and warranty buying checks.'}}


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_preserves_accurate_description_and_repairs_bad_descriptions(market):
    row = article(market)
    text, issues = choose_description(row, market)
    assert text == row['_seo']['description']
    assert issues == []
    for bad in ['', 'Best deals', 'Buy tablets in the UK with guaranteed lowest price £99.99 today.',
                'Compare coffee makers in the USA with cellular features and warranty.', '{description}']:
        broken = copy.deepcopy(row)
        broken['_seo']['description'] = bad
        text, issues = choose_description(broken, market)
        assert issues and len(text) <= 155
        assert CONFIG[market]['region'] in text
        assert 'Coffee' in text and 'warranty' in text
        assert 'cellular' not in text and '£99.99' not in text


def test_duplicate_description_uses_page_specific_title_and_supported_features():
    row = article()
    duplicate = row['_seo']['description'].casefold()
    text, issues = choose_description(row, 'uk', [duplicate])
    assert 'description duplicated across articles' in issues
    assert text != row['_seo']['description']
    row['title'] = 'Compact Coffee Machines Worth Buying in the UK (2026)'
    assert choose_description(row, 'uk', [duplicate])[0] != text


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_affiliate_repair_preserves_destinations_copy_images_and_unrelated_links(market):
    config = CONFIG[market]
    body = (f'<p>Manual copy</p><img src="manual.jpg"><a class="button" href="https://www.{config["ebay"]}/itm/123?foo=bar&campid=wrong" rel="noopener">eBay</a>'
            f'<a href="https://www.{config["amazon"]}/dp/ABC?tag=wrong">Amazon</a>'
            '<a href="https://www.ebay.com.evil.test/itm/123">Unrelated</a>')
    repaired = repair_affiliate_links(body, market, 'coffee-guide')
    assert '<p>Manual copy</p><img src="manual.jpg">' in repaired
    assert 'class="button"' in repaired and '>eBay</a>' in repaired
    assert 'https://www.ebay.com.evil.test/itm/123' in repaired
    assert repaired == repair_affiliate_links(repaired, market, 'coffee-guide')
    from src.publication_quality import ANCHOR, HREF, REL
    links = [{'href': html.unescape(HREF.search(tag).group(2)), 'rel': REL.search(tag).group(2) if REL.search(tag) else ''} for tag in ANCHOR.findall(repaired)]
    assert affiliate_issues(links, market, 'coffee-guide') == []
    assert affiliate_issues(links, market, 'different-guide')
    assert parse_qs(urlsplit(links[0]['href']).query)['foo'] == ['bar']


def test_metadata_repair_failure_does_not_block_a_published_post():
    row = article()
    post = {'id': '1', 'content': '<p>Manual copy</p>'}
    class Client:
        def update_post_content(self, *args):
            raise RuntimeError('temporary Blogger failure')
    assert repair_metadata(Client(), post, row, 'uk') is post


def test_fallback_listener_shares_theme_guard_and_metadata_is_idempotent():
    row = article()
    content = enrich_metadata('<p>Manual copy</p>', row, 'uk')
    assert 'if (window.wbRetailerMeasurement) return;' in content
    assert 'wb-retailer-fallback' in content
    assert enrich_metadata(content, row, 'uk') == content


def observed(row, market='uk'):
    from src.publishing_seo import description_for
    return {'articlePresent': True, 'description': [description_for(row, market)],
            'ogDescription': [description_for(row, market)], 'canonical': 'https://www.worthbuyinguk.co.uk/2026/10/coffee.html',
            'links': [], 'configuredProperties': [CONFIG[market]['property']], 'gtagPresent': True,
            'testedRetailerLink': True, 'events': [['event', 'wb_retailer_click', {'article_slug': row['slug'], 'send_to': CONFIG[market]['property']}]]}


def test_actual_rendered_description_duplicate_events_and_wrong_property_are_detected():
    row = article()
    good = observed(row)
    assert assess(good, row, 'uk', good['canonical'])['verification'] == 'passed'
    for key, value in [('description', ['Wrong']), ('description', good['description'] * 2),
                       ('events', good['events'] * 2), ('configuredProperties', [CONFIG['us']['property']])]:
        bad = {**good, key: value}
        assert assess(bad, row, 'uk', good['canonical'])['verification'] == 'needs_attention'
    result = assess(good, row, 'uk', good['canonical'])
    assert 'not tested' in result['ga4_receipt']


def test_repair_rechecks_and_preserves_editorial_copy():
    row = article()
    class Client:
        content = '<p>Manually improved guide</p><img src="manual.jpg">'
        def get_post(self, *args):
            return {'id': '1', 'content': self.content}
        def update_post_content(self, post_id, content):
            self.content = content
    client = Client()
    calls = []
    def probe(*args):
        calls.append(1)
        return {'verification': 'passed' if len(calls) == 2 else 'needs_attention',
                'issues': [] if len(calls) == 2 else ['rendered description missing']}
    result = verify_one(probe, row, 'uk', {'post_id': '1', 'url': 'https://www.worthbuyinguk.co.uk/2026/10/coffee.html'}, client)
    assert result['verification'] == 'passed' and len(calls) == 2
    assert client.content.startswith('<p>Manually improved guide</p><img src="manual.jpg">')


def test_browser_failure_is_unconfirmed_and_never_overwrites_the_post():
    class Client:
        def get_post(self, *args):
            raise AssertionError('No repair without a valid browser diagnosis')
    def probe(*args):
        raise TimeoutError()
    result = verify_one(probe, article(), 'uk', {'post_id': '1', 'url': 'https://www.worthbuyinguk.co.uk/2026/10/coffee.html'}, Client())
    assert result['verification'] == 'unconfirmed'
    assert 'TimeoutError' in result['issues']
