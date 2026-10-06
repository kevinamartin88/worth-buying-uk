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
