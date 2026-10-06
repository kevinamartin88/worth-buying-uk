import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.us_targeting import (localize_html, prepare_us_article, us_article_output,
                              us_audience_hours, us_url, validate_us_copy, validate_retailer)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('copy', ['colour', 'organisers', 'tyres', 'postcode', '£25', 'GBP 25',
                                  'UK shoppers', 'VAT included', 'https://www.amazon.co.uk/dp/B123456789',
                                  'https://www.ebay.co.uk/itm/123', 'https://www.worthbuyinguk.co.uk/',
                                  'https://www.amazon.ca/', 'https://worthbuyingusa.blogspot.com/2026/post.html'])
def test_rejects_common_uk_copy_and_foreign_domains(copy):
    with pytest.raises(ValueError):
        validate_us_copy(copy)


def test_localizes_display_without_corrupting_links_models_or_scripts():
    body = '<p>Colour organisers 5 litres</p><a href="https://www.ebay.com/itm/colour-5-litre">View</a><script>const colour = 1;</script>'
    result = localize_html(body)
    assert '<p>Color organizers 5.3 US quarts (approximately; 5 liters)</p>' in result
    assert 'https://www.ebay.com/itm/colour-5-litre' in result
    assert '<script>const colour = 1;</script>' in result
    assert localize_html(result) == result


def test_preparation_is_idempotent_and_does_not_mutate_source():
    original = {'slug': 'tyre-test', 'title': 'Tyre inflators', 'content_html': '<p>Check your postcode.</p>'}
    clean = prepare_us_article(original)
    assert clean['title'] == 'Tire inflators'
    assert clean['slug'] == original['slug']
    assert clean['_seo']['language'] == 'en-US'
    assert clean['_seo']['site_url'] == 'https://www.worthbuyingusa.com/'
    assert 'inches or feet' in clean['content_html']
    assert original['title'] == 'Tyre inflators'
    assert prepare_us_article(clean) == clean


def test_shared_builder_preserves_uk_output():
    original = {'title': 'Colour organisers UK', 'content_html': '<p>£10</p>'}
    @us_article_output
    def build(market):
        return original
    assert build('uk') is original


@pytest.mark.parametrize('url', ['https://www.worthbuyinguk.co.uk/post', 'https://worthbuyingusa.com.evil.test/', 'https://example.com/', 'https://user@www.worthbuyingusa.com/'])
def test_usa_url_rejects_wrong_site(url):
    with pytest.raises(ValueError):
        us_url(url)


def test_known_blogger_aliases_keep_existing_path():
    for host in ('worthbuyingusa.blogspot.com', 'worthbuyingusa.com', 'www.worthbuyingusa.com'):
        assert us_url(f'http://{host}/2026/10/existing.html?x=1') == 'https://www.worthbuyingusa.com/2026/10/existing.html?x=1'


def test_social_copy_links_only_to_usa():
    validate_us_copy('Read https://www.worthbuyingusa.com/post', social=True)
    for host in ('www.worthbuyinguk.co.uk', 'www.amazon.com', 'worthbuyingusa.com', 'example.com'):
        with pytest.raises(ValueError):
            validate_us_copy(f'Read https://{host}/post', social=True)


def test_affiliate_destination_must_be_a_us_merchant():
    validate_retailer('https://click.linksynergy.com/deeplink?murl=https%3A%2F%2Fwww.sharperimage.com%2Fp')
    for url in ('https://click.linksynergy.com/deeplink', 'https://click.linksynergy.com/deeplink?murl=https%3A%2F%2Fwww.amazon.co.uk%2Fp', 'https://unknown-retailer.com/p'):
        with pytest.raises(ValueError):
            validate_us_copy(f'<a href="{url}" rel="sponsored nofollow">Buy</a>')


@pytest.mark.parametrize('date,hour,allowed', [('2026-07-06',12,False), ('2026-07-06',13,True), ('2026-01-06',13,False), ('2026-01-06',14,True), ('2026-01-06',2,False)])
def test_eastern_window_handles_dst(date, hour, allowed):
    assert us_audience_hours(datetime.fromisoformat(f'{date}T{hour:02}:00:00+00:00')) is allowed


def test_usa_google_shopping_payload_and_cache_are_explicit_us(monkeypatch, tmp_path):
    from src import google_shopping_trends as shopping, shopping_cache as cache
    monkeypatch.setattr(cache, 'CACHE_PATH', tmp_path / 'cache.json')
    topic = ('tires', 'Tire inflators', 'tire inflator')
    cache.remember('us', [(topic, {'query': 'tire inflator', 'score': 90, 'geo': 'GB'})])
    assert cache.cached_topics([topic], 'us') == []
    session = Mock()
    session.get.return_value.json = lambda: {}
    session.get.return_value.text = '{"widgets": []}'
    shopping._explore_widgets(session, ['tire inflator'], 'US', 'en-US')
    params = session.get.call_args.kwargs['params']
    assert params['hl'] == 'en-US'
    assert json.loads(params['req'])['comparisonItem'][0]['geo'] == 'US'
    assert json.loads(params['req'])['property'] == 'froogle'


def test_usa_trends_request_uses_us_and_usa_referer(monkeypatch):
    from src import google_trends
    captured = []
    def unavailable(request, **kwargs):
        captured.append(request)
        raise OSError('offline fixture')
    monkeypatch.setattr(google_trends.urllib.request, 'urlopen', unavailable)
    assert google_trends.fetch_trending_searches('us') == []
    assert captured[0].full_url.endswith('geo=US')
    assert 'www.worthbuyingusa.com' in captured[0].get_header('User-agent')


def test_all_stored_usa_articles_are_clean():
    for file in (ROOT / 'articles-us').glob('*.json'):
        article = json.loads(file.read_text(encoding='utf-8'))
        assert prepare_us_article(article) == article, file.name


def test_usa_channel_never_falls_back_to_the_only_uk_account():
    from src.buffer import BufferClient
    client = BufferClient('fixture', 'Worth Buying USA')
    client._graphql = Mock(side_effect=[{'account': {'organizations': [{'id': 'org'}]}},
        {'channels': [{'id': 'uk', 'name': 'Worth Buying UK', 'service': 'twitter'}]}])
    with pytest.raises(RuntimeError, match='USA Buffer'):
        client.find_x_channel_id()


def test_workflow_defers_usa_without_changing_uk_schedule():
    import yaml
    us = yaml.safe_load((ROOT / '.github/workflows/publish-articles-us.yml').read_text())
    trigger = us.get('on', us.get(True))
    assert trigger['schedule'][0]['cron'] == '23 14,17,21 * * *'
    assert us['jobs']['publish-us']['needs'] == 'usa-time-gate'
    uk = yaml.safe_load((ROOT / '.github/workflows/daily-article-creator.yml').read_text())
    assert uk.get('on', uk.get(True))['schedule'][0]['cron'] == '7 23,0-6 * * *'


def test_air_fryer_image_prompt_and_cache_version_are_usa_only():
    from src.ai_visuals import build_prompt
    from src.article_images import hero_image_url
    article = {'title': 'Large Capacity Air Fryers Worth Comparing'}
    assert 'pull-out basket handles' in build_prompt(article, 'us')
    assert 'No freestanding oven' in build_prompt(article, 'us')
    slug = 'best-large-capacity-air-fryers-worth-buying-us'
    assert hero_image_url('us', slug).endswith('?v=basket-air-fryers-v2')
    assert '?v=' not in hero_image_url('uk', slug)
