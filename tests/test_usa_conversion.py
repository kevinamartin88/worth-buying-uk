from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import json

import pytest
import requests
import yaml

import generate_daily_articles as daily
import refresh_usa_conversion_pilot as pilot
from src.usa_conversion import relevant_product, live_listing, cards_html, tracking_script, amazon_direct, PILOT_TOPICS


def item(n=1, price=80):
    return {
        'itemId': f'v1|{n}|0', 'title': f'Dyson V{n} cordless stick vacuum cleaner',
        'brand': 'Dyson', 'condition': 'New', 'buyingOptions': ['FIXED_PRICE'],
        'itemWebUrl': f'https://www.ebay.com/itm/{n}',
        'price': {'value': str(price), 'currency': 'USD'},
        'seller': {'feedbackPercentage': 99.9, 'feedbackScore': 5000},
        'listingMarketplaceId': 'EBAY_US', 'itemLocation': {'country': 'US'},
        'estimatedAvailabilities': [{'estimatedAvailabilityStatus': 'IN_STOCK', 'estimatedAvailableQuantity': 2}],
        'image': {'imageUrl': f'https://i.ebayimg.com/images/g/{n}/s-l1600.jpg'},
        'shippingOptions': [{'shippingCost': {'value': '5', 'currency': 'USD'}}],
        'localizedAspects': [{'name': 'Brand', 'value': 'Dyson'}],
    }


@pytest.mark.parametrize('title,query', [
    ('Cordless handheld mini car vacuum cleaner', 'cordless vacuum'),
    ('Samsung SSD enclosure adapter', 'SSD drive'),
    ('SSD heatsink', 'SSD drive'),
    ('Slow cooker replacement lid', 'slow cooker'),
    ('Portable espresso machine adapters kit', 'coffee maker'),
    ('Air fryer liners', 'air fryer'),
])
def test_accessories_and_wrong_product_types_are_rejected(title, query):
    assert not relevant_product(title, query)


@pytest.mark.parametrize('title,query', [
    ('Dyson V8 cordless stick vacuum cleaner', 'cordless vacuum'),
    ('Samsung 990 EVO 1TB SSD', 'SSD drive'),
    ('Crock-Pot 7 quart slow cooker', 'slow cooker'),
    ('Ninja air fryer', 'air fryer'),
    ('Coffee maker with built-in grinder', 'coffee maker'),
    ('iPhone protective case', 'iPhone case'),
])
def test_real_products_and_other_accessory_categories_still_pass(title, query):
    assert relevant_product(title, query)


@pytest.mark.parametrize('field,value', [
    ('estimatedAvailabilities', []),
    ('estimatedAvailabilities', [{'estimatedAvailabilityStatus': 'OUT_OF_STOCK'}]),
    ('itemEndDate', '2026-01-01T00:00:00Z'),
    ('itemEndDate', 'bad'),
    ('listingMarketplaceId', 'EBAY_GB'),
    ('itemLocation', {'country': 'GB'}),
    ('price', {'value': 'NaN', 'currency': 'USD'}),
    ('itemWebUrl', 'https://www.ebay.com.evil.test/itm/1'),
])
def test_unavailable_or_cross_market_items_fail(field, value):
    row = item()
    row[field] = value
    assert not live_listing(row, datetime(2026, 10, 5, tzinfo=timezone.utc))


def test_cards_show_evidence_images_shipping_and_honest_search_labels():
    rows = [item(1, 100), item(2, 60), item(3, 90), item(4, 110)]
    text = cards_html(rows, daily.retailer_urls, 'cordless vacuum')
    assert text.count('class="wb-buying-card"') == 3
    assert text.count('class="wb-product-image"') == 3
    assert '$65.00 before sales tax' in text
    assert 'Brand: Dyson' in text
    assert 'Lowest checked listing price' in text
    assert 'Search Amazon for alternatives' in text
    assert 'exact match and price not verified' in text
    assert 'Check Amazon price' not in text
    assert 'Before buying' in text
    assert 'data-wb-placement="quick-pick"' in text


def test_verified_amazon_offer_links_directly_with_a_price():
    row = item()
    row['_amazon_offer'] = {'url': 'https://www.amazon.com/dp/B012345678', 'price': 90.0, 'currency': 'USD'}
    text = cards_html([row], daily.retailer_urls, 'cordless vacuum')
    assert 'Check this model on Amazon — $90.00' in text
    assert 'Search Amazon for alternatives' not in text
    assert not amazon_direct({'url': 'https://www.amazon.co.uk/dp/B012345678', 'price': 90, 'currency': 'GBP'})
    assert not amazon_direct({'url': 'https://www.amazon.com/s?k=Dyson', 'price': 90, 'currency': 'USD'})


def test_live_details_and_image_quality_gate_us_shortlist(monkeypatch):
    client = Mock()
    rows = [item(1), item(2), item(3)]
    client.search.return_value = rows
    sold = item(2)
    sold['estimatedAvailabilities'][0]['estimatedAvailabilityStatus'] = 'OUT_OF_STOCK'
    client.get_item.side_effect = [item(1), sold, item(3)]
    monkeypatch.setattr(daily.EbayClient, 'for_market', lambda market: client)
    monkeypatch.setattr(daily, '_record_price_history', lambda *args: None)
    monkeypatch.setattr('src.product_image_quality.checked_product_image', lambda url: (url, 1600, 1200))
    result = daily.current_picks('us', 'cordless vacuum', 700, 'vacuum-guide')
    assert {r['itemId'] for r in result} == {'v1|1|0', 'v1|3|0'}


def test_usa_article_puts_real_choices_before_methodology_and_reuses_slug(monkeypatch):
    rows = [item(1), item(2), item(3)]
    monkeypatch.setattr(daily, 'current_picks', lambda *args: rows)
    monkeypatch.setattr(daily, 'add_amazon_prices', lambda *args: None)
    monkeypatch.setattr(daily, 'related_guides', lambda **kwargs: [])
    topic = next(t for t in daily.TOPICS if t[0] == 'cordless-vacuums')
    article = daily.build_article(topic, 'us', 2026)
    body = article['content_html']
    assert body.index('Check this listing on eBay') < body.index('For this guide, our automation')
    assert body.count('class="wb-buying-card"') == 3
    assert article['slug'] == 'best-cordless-vacuums-worth-buying-us-2026'
    assert 'data-wb-article=' in body
    assert article['_monetisation']['version'] == 'usa-buying-cards-v1'


def test_pilot_prepares_all_five_before_writing(monkeypatch, tmp_path):
    (tmp_path / 'articles-us').mkdir()
    topics = {t[0]: t for t in daily.TOPICS}
    for key in PILOT_TOPICS:
        (tmp_path / 'articles-us' / f'{key}.json').write_text(json.dumps({'slug': key}))
    calls = []
    def build(topic, market, year):
        calls.append(topic[0])
        return {'slug': topic[0], '_generator': {'live_ebay_picks': topic[0] != 'ssds', 'pick_count': 3}}
    monkeypatch.setattr(daily, 'ROOT', tmp_path)
    monkeypatch.setattr(daily, 'build_article', build)
    with pytest.raises(RuntimeError, match='ssds'):
        pilot.main()
    assert daily.load_json(tmp_path / 'articles-us' / 'cordless-vacuums.json') == {'slug': 'cordless-vacuums'}
    assert not (tmp_path / 'state/usa_conversion_pilot.json').exists()


def test_tracking_does_not_install_an_unknown_property_or_block_navigation():
    script = tracking_script('guide')
    assert 'wb_retailer_click' in script
    assert "typeof window.gtag !== 'function'" in script
    assert 'preventDefault' not in script
    assert 'googletagmanager.com/gtag/js' not in script
    assert 'googletagmanager.com/gtag/js?id=G-ABC123' in tracking_script('guide', 'G-ABC123')
    with pytest.raises(ValueError):
        tracking_script('guide', '<script>')


def test_legacy_manual_guide_keeps_its_existing_slug(monkeypatch, tmp_path):
    slug = 'best-air-fryers-worth-buying-us-2026'
    (tmp_path / f'{slug}.json').write_text(json.dumps({'slug': slug, 'title': 'Best Air Fryers'}))
    monkeypatch.setattr(daily, 'published_article_dir', lambda market: tmp_path)
    assert daily.evergreen_article_slug('air-fryers', 'us') == slug


def test_pilot_workflow_explicitly_hands_off_to_usa_publisher():
    root = Path(__file__).resolve().parents[1]
    wf = yaml.safe_load((root / '.github/workflows/usa-conversion-pilot.yml').read_text())
    assert wf['permissions']['actions'] == 'write'
    steps = wf['jobs']['refresh-five']['steps']
    assert steps[-1]['run'] == 'gh workflow run publish-articles-us.yml --ref main'
    assert 'GH_TOKEN' in steps[-1]['env']
