from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
import html
import re

import pytest
import requests
import yaml
from pathlib import Path

from src.ebay_deals import discover, revalidate, render, validate_item, TITLES, TRACKING
from refresh_ebay_deals import refresh, EXPECTED_HOSTS

NOW = datetime(2026, 10, 5, 6, 17, tzinfo=timezone.utc)


def listing(market='uk'):
    currency = 'GBP' if market == 'uk' else 'USD'
    return {
        'itemId': 'v1|123|0', 'title': 'Cordless vacuum cleaner',
        'itemWebUrl': 'https://www.ebay.co.uk/itm/123' if market == 'uk' else 'https://www.ebay.com/itm/123',
        'price': {'value': '80', 'currency': currency},
        'marketingPrice': {'discountPercentage': '20', 'originalPrice': {'value': '100', 'currency': currency}},
        'buyingOptions': ['FIXED_PRICE'], 'condition': 'New',
        'listingMarketplaceId': 'EBAY_GB' if market == 'uk' else 'EBAY_US',
        'itemLocation': {'country': 'GB' if market == 'uk' else 'US'},
        'seller': {'feedbackPercentage': '99', 'feedbackScore': 1000},
        'estimatedAvailabilities': [{'estimatedAvailabilityStatus': 'IN_STOCK', 'estimatedAvailableQuantity': 5}],
        'shippingOptions': [{'shippingCost': {'value': '0', 'currency': currency}}],
        'itemEndDate': '2026-11-01T00:00:00Z',
    }


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_correct_market_tracking_and_metadata(market):
    deal = validate_item(listing(market), market, 500, NOW)
    deal.update(topic='vacuums', ceiling=500)
    content = render([deal], market, NOW, NOW.isoformat())
    href = html.unescape(re.search(r'href="([^"]+)"', content)[1])
    assert parse_qs(urlsplit(href).query)['campid'] == [TRACKING[market]['campid']]
    assert parse_qs(urlsplit(href).query)['customid'] == [f'weekly-ebay-deals-{market}']
    client = Mock()
    client.get_item.return_value = listing(market)
    found, stamp = revalidate(client, market, content, NOW)
    assert len(found) == 1 and stamp == NOW.isoformat()
    with pytest.raises(ValueError, match='market'):
        revalidate(client, 'us' if market == 'uk' else 'uk', content, NOW)


@pytest.mark.parametrize('field,value', [
    ('itemEndDate', '2026-10-05T06:16:00Z'),
    ('itemEndDate', '2026-10-06T05:00:00Z'),
    ('itemEndDate', 'invalid'),
    ('estimatedAvailabilities', [{'estimatedAvailabilityStatus': 'OUT_OF_STOCK'}]),
    ('estimatedAvailabilities', [{'estimatedAvailabilityStatus': 'IN_STOCK', 'estimatedAvailableQuantity': 0}]),
    ('estimatedAvailabilities', []),
    ('listingMarketplaceId', 'EBAY_US'),
    ('itemLocation', {'country': 'US'}),
    ('price', {'value': 'NaN', 'currency': 'GBP'}),
    ('price', {'value': '-10', 'currency': 'GBP'}),
    ('price', {'value': '600', 'currency': 'GBP'}),
    ('price', {'value': '80', 'currency': 'USD'}),
    ('seller', {'feedbackPercentage': '90', 'feedbackScore': 1000}),
    ('seller', {}),
    ('shippingOptions', []),
    ('buyingOptions', ['AUCTION']),
    ('title', 'Vacuum cleaner for parts'),
    ('title', 'Replacement filter for cordless vacuum'),
    ('conditionId', '7000'),
    ('itemWebUrl', 'https://www.ebay.com/itm/123'),
    ('itemWebUrl', 'https://www.ebay.co.uk.evil.test/itm/123'),
    ('itemWebUrl', 'https://user:password@www.ebay.co.uk/itm/123'),
    ('marketingPrice', {'discountPercentage': 90, 'originalPrice': {'value': 100, 'currency': 'GBP'}}),
])
def test_invalid_listings_are_rejected(field, value):
    item = listing()
    item[field] = value
    assert validate_item(item, 'uk', 500, NOW) is None


def test_details_override_stale_search_and_deduplicate():
    client = Mock()
    summary = listing()
    client.search.return_value = [summary, deepcopy(summary)]
    sold_out = listing()
    sold_out['estimatedAvailabilities'][0]['estimatedAvailabilityStatus'] = 'OUT_OF_STOCK'
    client.get_item.return_value = sold_out
    assert discover(client, 'uk', NOW) == []
    assert client.get_item.call_count == 1


def test_daily_recheck_removes_lost_discount_and_missing_listing():
    item = listing()
    deal = validate_item(item, 'uk', 500, NOW)
    deal.update(topic='vacuums', ceiling=500)
    content = render([deal], 'uk', NOW, NOW.isoformat())
    item.pop('marketingPrice')
    client = Mock()
    client.get_item.return_value = item
    assert revalidate(client, 'uk', content, NOW)[0] == []
    client.get_item.side_effect = requests.HTTPError(response=Mock(status_code=404))
    assert revalidate(client, 'uk', content, NOW)[0] == []
    client.get_item.side_effect = requests.HTTPError(response=Mock(status_code=429))
    with pytest.raises(requests.HTTPError):
        revalidate(client, 'uk', content, NOW)


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_refresh_updates_stable_deals_section_and_clears_empty_results(market):
    ebay, blogger = Mock(), Mock()
    ebay.search.return_value = []
    blogger.upsert_post.return_value = {'id': '42', 'url': 'https://site/existing'}
    blogger.get_post_or_none.return_value = {'id': '42', 'content': render([], market, NOW, NOW.isoformat())}
    result = refresh(market, 'discover', ebay, blogger, NOW)
    assert result['id'] == '42'
    blogger.resolve_blog.assert_called_once_with(EXPECTED_HOSTS[market], TITLES[market])
    title, content = blogger.upsert_post.call_args.args
    assert title == TITLES[market]
    assert 'No verified eBay deals' in content
    assert 'Deals' in blogger.upsert_post.call_args.kwargs['labels']


def test_source_failure_never_publishes_old_or_partial_results():
    ebay, blogger = Mock(), Mock()
    ebay.search.side_effect = requests.HTTPError(response=Mock(status_code=401))
    with pytest.raises(requests.HTTPError):
        refresh('uk', 'discover', ebay, blogger, NOW)
    blogger.upsert_post.assert_not_called()


def test_workflow_runs_both_markets_with_weekly_discovery_and_daily_validation():
    path = Path(__file__).resolve().parents[1] / '.github/workflows/weekly-ebay-deals.yml'
    workflow = yaml.safe_load(path.read_text())
    events = workflow.get('on', workflow.get(True))
    assert {s['cron'] for s in events['schedule']} == {'17 6 * * 1', '17 6 * * 0,2-6'}
    job = workflow['jobs']['refresh']
    assert job['strategy']['fail-fast'] is False
    markets = job['strategy']['matrix']['include']
    assert {r['market'] for r in markets} == {'uk', 'us'}
    assert len({r['blog_id'] for r in markets}) == 2
    step = job['steps'][-1]
    assert "'validate'" in step['env']['MODE']
    assert 'SMTP' not in str(step['env'])



def test_validate_missing_roundup_is_clean_skip(monkeypatch, capsys):
    from datetime import datetime, timezone
    import refresh_ebay_deals as refresh_module

    blogger = Mock()
    blogger.resolve_blog.return_value = {}
    blogger.find_post_by_exact_title.return_value = None
    ebay = Mock()

    result = refresh_module.refresh(
        "us",
        "validate",
        ebay,
        blogger,
        datetime(2026, 10, 6, tzinfo=timezone.utc),
    )

    assert result is None
    assert "weekly roundup does not exist yet" in capsys.readouterr().out
    ebay.search.assert_not_called()
    blogger.upsert_post.assert_not_called()


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_roundup_has_real_jpeg_hero_even_without_offers(market):
    from src.article_images import require_hero_image
    from PIL import Image
    slug = f'weekly-ebay-deals-{market}'
    path = Path(__file__).resolve().parents[1] / 'assets/ai' / market / f'{slug}.jpg'
    with Image.open(path) as image:
        assert image.format == 'JPEG' and image.size == (1600, 900)
    content = render([], market, NOW, NOW.isoformat())
    assert content.startswith('<div class="wb-article-hero"')
    assert require_hero_image(market, slug) in content
    assert '<svg' not in content and '.svg' not in content


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_image_repair_preserves_live_copy_and_is_idempotent(market):
    from src.article_images import hero_image_html
    ebay, blogger = Mock(), Mock()
    original = '<p>Manually checked offers and exact prices</p><!-- wb-ebay-deals:metadata -->'
    hero, _ = hero_image_html(market, f'weekly-ebay-deals-{market}', TITLES[market])
    repaired = hero + original
    blogger.find_post_by_exact_title.return_value = {'id': '42'}
    blogger.get_post_or_none.side_effect = [
        {'id': '42', 'content': original}, {'id': '42', 'content': repaired},
        {'id': '42', 'content': repaired}, {'id': '42', 'content': repaired},
    ]
    refresh(market, 'repair-images', ebay, blogger, NOW)
    refresh(market, 'repair-images', ebay, blogger, NOW)
    blogger.update_post_content.assert_called_once_with('42', repaired)
    blogger.upsert_post.assert_not_called()
    ebay.search.assert_not_called()
    ebay.get_item.assert_not_called()


def test_image_repair_fails_if_blogger_drops_the_image():
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = {'id': '42'}
    blogger.get_post_or_none.return_value = {'id': '42', 'content': '<p>Offers</p>'}
    with pytest.raises(RuntimeError, match='without the required hero'):
        refresh('uk', 'repair-images', Mock(), blogger, NOW)


def test_push_repairs_images_without_refreshing_offer_prices():
    path = Path(__file__).resolve().parents[1] / '.github/workflows/weekly-ebay-deals.yml'
    workflow = yaml.safe_load(path.read_text())
    mode = workflow['jobs']['refresh']['steps'][-1]['env']['MODE']
    assert "github.event_name == 'push' && 'repair-images'" in mode
