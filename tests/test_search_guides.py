import copy
import re

import pytest

from src.search_guides import enhance_search_guide, START, FAQ_START


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_enrichment_preserves_prices_links_tracking_and_publication_identity(market):
    body = ('<div><p>Prices checked: 10 October 2026</p>'
            '<img src="photo.jpg" alt="Product">'
            '<a href="https://www.ebay.com/itm/123?campid=456" rel="sponsored nofollow">$100</a>'
            '<h2>How to choose the right option</h2><p>Generic advice.</p>'
            '<h2>Retailer comparison</h2><p>Keep this.</p>'
            '<h2>Frequently asked questions</h2><h3>Old question</h3><p>Old answer</p>'
            '<p style="margin:18px 0"><a href="https://example.com/hub">Explore</a></p>'
            '<h2>Related Worth Buying guides</h2><p>Keep related.</p>'
            '</div><script>wb_retailer_click</script>')
    article = {'slug': 'existing-slug', 'title': 'Existing title', 'content_html': body,
               '_generator': {'topic': 'pressure-washers'}, '_seo': {'secondary_keywords': []},
               '_promotion': {'promotion_token': 'unchanged', 'daily_featured_date': '2026-10-10'}}
    before = copy.deepcopy(article)
    result = enhance_search_guide(article, market)
    assert article == before
    for key in ['slug', 'title', '_generator', '_promotion']:
        assert result[key] == article[key]
    for pattern in [r'<a[^>]*>.*?</a>', r'<img[^>]*>', r'<script>.*?</script>']:
        old = re.findall(pattern, body)
        assert all(fragment in result['content_html'] for fragment in old)
    assert 'Prices checked: 10 October 2026' in result['content_html']
    assert 'Generic advice' not in result['content_html']
    assert 'Old question' not in result['content_html']
    assert 'Keep related.' in result['content_html']
    assert enhance_search_guide(result, market) == result
    assert result['content_html'].count(START) == 1
    assert result['content_html'].count(FAQ_START) == 1
    assert len(result['_seo']['description']) <= 155
    assert ('litres per hour' if market == 'uk' else 'GPM') in result['content_html']
    assert ('/gb/en/' if market == 'uk' else '/us/en/') in result['content_html']


def test_other_topics_and_unknown_market_are_unchanged():
    article = {'content_html': '<p>Original</p>', '_generator': {'topic': 'air-fryers'}}
    assert enhance_search_guide(article, 'uk') is article
    article['_generator']['topic'] = 'pressure-washers'
    assert enhance_search_guide(article, 'unknown') is article


def test_old_unstructured_content_remains_and_enrichment_is_idempotent():
    article = {'content_html': '<p>Old retailer copy</p>', '_generator': {'topic': 'pressure-washers'}}
    result = enhance_search_guide(article, 'uk')
    assert '<p>Old retailer copy</p>' in result['content_html']
    assert enhance_search_guide(result, 'uk') == result


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_daily_generator_retains_advice_even_without_live_listings(monkeypatch, market):
    from datetime import datetime
    import generate_daily_articles as daily

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 14, 12, tzinfo=tz)

        def strftime(self, fmt):
            return super().strftime(fmt.replace('%-d', '%d'))

    monkeypatch.setattr(daily, 'datetime', FixedDateTime)
    monkeypatch.setattr(daily, 'current_picks', lambda *args: [])
    monkeypatch.setattr(daily, 'related_guides', lambda **kwargs: [])
    topic = next(row for row in daily.TOPICS if row[0] == 'pressure-washers')
    article = daily.build_article(topic, market, 2026, is_refresh=True)
    assert START in article['content_html']
    assert FAQ_START in article['content_html']
    assert article['_seo']['editorial_revision'] == 'pressure-search-guide-v1'
    assert article['_generator']['live_ebay_picks'] is False
    assert article['_promotion']['is_refresh'] is True
    assert 'sponsored nofollow' in article['content_html']
    if market == 'us':
        assert 'wb_retailer_click' in article['content_html']
