import copy
import json
from pathlib import Path

import pytest

from src.uk_editorial import (ADVICE, FURNITURE, START, enhance_uk_article,
    enhance_uk_savvy, relevant_uk_product, weekly_deal_advice, uk_text)


@pytest.mark.parametrize('topic', list(ADVICE) + list(FURNITURE))
def test_specific_advice_is_repeatable_and_preserves_commerce(topic):
    g = {'topic': topic}
    target = 'How to choose the right option'
    if topic in FURNITURE:
        g['channel'] = 'rakuten'
        target = 'How to compare these retailer offers'
    if topic == 'tower-fans':
        target = 'What should you look for?'
    body = ('<p>Prices checked: 2026-10-20</p><img src="photo.jpg">'
        '<a href="https://www.ebay.co.uk/itm/123?campid=456" data-wb-retailer="ebay">Offer</a>'
        '<p><strong>Shopping for a product in the UK? Repeated intro.</strong></p>'
        '<h2>' + target + '</h2><p>Generic</p>'
        '<h2>eBay UK vs Amazon UK: where should you compare?</h2><p>Repeated retailer text</p>'
        '<h2>Evidence</h2><p>Keep evidence</p>'
        '<h2>Frequently asked questions</h2><h3>Generic question</h3><p>Old answer</p>'
        '<p><em>Affiliate disclosure: keep this.</em></p>'
        '<h2>Related Worth Buying guides</h2><a href="/p/hub.html">Hub</a>')
    a = {'slug': 'stable', 'title': 'Stable', 'source_sha': 'same', 'content_html': body,
         '_generator': g, '_promotion': {'promotion_token': 'same'}}
    old = copy.deepcopy(a)
    b = enhance_uk_article(a, 'uk')
    assert a == old
    assert enhance_uk_article(b, 'uk') == b
    assert enhance_uk_article(a, 'us') is a
    for key in ('slug', 'title', 'source_sha', '_generator', '_promotion'):
        assert b[key] == a[key]
    for fragment in ('Prices checked: 2026-10-20', 'photo.jpg', 'campid=456',
                     'data-wb-retailer="ebay"', 'Keep evidence', 'Affiliate disclosure: keep this.', '/p/hub.html'):
        assert fragment in b['content_html']
    assert 'Generic question' not in b['content_html']
    assert 'Repeated intro' not in b['content_html']
    assert START in b['content_html']


@pytest.mark.parametrize('title,query,expected', [
    ('One For All Smart Streamer Universal Remote', 'streaming device', False),
    ('Fire TV Stick 4K with Remote', 'streaming device', True),
    ('Replacement remote for Fire TV Stick 4K', 'streaming device', False),
    ('TP Link Wi-Fi Smart Plug EU PLUG', 'smart plug', False),
    ('TP Link Wi-Fi Smart Plug UK PLUG', 'smart plug', True),
    ('Philips GoPure In-Car Air Purifier', 'air purifier', False),
    ('Shark Room Air Purifier HP072UK', 'air purifier', True),
])
def test_uk_product_type_and_plug_checks(title, query, expected):
    assert relevant_uk_product(title, query) is expected


def test_unknown_and_sourced_articles_are_preserved():
    for topic in ('unknown', 'backpacks'):
        a = {'_generator': {'topic': topic}, 'content_html': '<h2>Researched advice</h2><p>Source</p>'}
        assert enhance_uk_article(a, 'uk') is a


def test_live_offer_notes_do_not_label_advice_as_products():
    a = {'_generator': {'topic': 'streaming-devices'}, 'content_html':
        '<h3>1. One For All Streaming Remote Control</h3><p>Offer</p>'
        '<h2>How to choose the right option</h2><p>Generic</p><h2>Evidence</h2>'}
    b = enhance_uk_article(a, 'uk')
    assert b['content_html'].count('class="wb-uk-offer-note"') == 1
    assert enhance_uk_article(b, 'uk') == b


def test_uk_corpus_descriptions_pass_actual_publication_rules():
    from src.publication_quality import choose_description, duplicate_descriptions
    duplicate_descriptions.cache_clear()
    duplicates = duplicate_descriptions('uk')
    for p in (Path(__file__).resolve().parents[1] / 'articles').glob('*.json'):
        a = json.loads(p.read_text(encoding='utf-8'))
        if not a.get('_seo', {}).get('uk_editorial_revision'):
            continue
        selected, issues = choose_description(a, 'uk', duplicates)
        assert not issues, (p.name, issues)
        assert selected == a['_seo']['description']
        assert enhance_uk_savvy(enhance_uk_article(a, 'uk'), 'uk') == a


def test_savvy_keeps_market_specific_examples_and_distinct_angles():
    bodies = []
    for angle in ('before-you-shop', 'compare-options', 'avoid-traps', 'final-checklist'):
        a = {'slug': f'savvy-buyer-saturday-price-comparison-{angle}-uk-2026-10-10',
             'title': 'Stable', 'source_sha': 'same', 'content_html': 'Repeated original'}
        b = enhance_uk_savvy(a, 'uk')
        assert b['title'] == a['title'] and b['source_sha'] == a['source_sha']
        assert len(b['content_html'].split()) >= 650
        assert '$' not in b['content_html'] and 'ZIP code' not in b['content_html']
        assert enhance_uk_savvy(b, 'uk') == b
        assert enhance_uk_savvy(a, 'us') is a
        bodies.append(b['content_html'])
    assert len(set(bodies)) == 4


def test_localisation_does_not_corrupt_words_and_roundup_explains_discount_basis():
    assert uk_text('entire tyre shipping cost') == 'entire tyre delivery cost'
    assert 'seller\'s stated reference price' in weekly_deal_advice()
