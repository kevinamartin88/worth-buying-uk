import copy
import re

import pytest

from src.usa_editorial import ADVICE, VARIANTS, START, enhance_usa_article, enhance_savvy_article
from src.usa_conversion import relevant_product


@pytest.mark.parametrize('topic', [*ADVICE, *VARIANTS])
def test_topic_advice_preserves_commerce_and_identity_and_is_repeatable(topic):
    body = ('<p>Prices checked: 2026-10-20</p><img src="photo.jpg">'
            '<a href="https://www.ebay.com/itm/123?campid=456" data-wb-retailer="ebay">Check offer</a>'
            '<h2>How to choose the right option</h2><ul><li>Generic</li></ul>'
            '<h2>eBay vs Amazon: where should you compare?</h2><p>Repeated</p>'
            '<h2>How we choose these daily picks</h2><p>Keep evidence</p>'
            '<h2>Frequently asked questions</h2><h3>Generic question</h3><p>Generic answer</p>'
            '<p><em>Affiliate disclosure: keep this.</em></p>'
            '<h2>Related Worth Buying guides</h2><a href="/p/hub.html">Hub</a>')
    article = {'slug': 'stable', 'title': 'Stable', 'source_sha': 'same', 'content_html': body,
               '_generator': {'topic': topic}, '_promotion': {'promotion_token': 'same'}}
    before = copy.deepcopy(article)
    result = enhance_usa_article(article, 'us')
    assert article == before
    assert enhance_usa_article(result, 'us') == result
    assert START in result['content_html']
    for key in ('slug', 'title', 'source_sha', '_generator', '_promotion'):
        assert result[key] == before[key]
    for fragment in ('Prices checked: 2026-10-20', '<img src="photo.jpg">',
                     'campid=456', 'data-wb-retailer="ebay"', 'Keep evidence',
                     'Affiliate disclosure: keep this.', '/p/hub.html'):
        assert fragment in result['content_html']
    assert 'Generic question' not in result['content_html']
    assert '<p>Repeated</p>' not in result['content_html']
    assert enhance_usa_article(article, 'uk') is article


def test_sourced_advice_and_unknown_topics_are_not_padded():
    for topic in ('blenders', 'unknown'):
        a = {'_generator': {'topic': topic}, 'content_html': '<h2>Researched advice</h2><p>Evidence</p>'}
        assert enhance_usa_article(a, 'us') is a


@pytest.mark.parametrize('title,query,expected', [
    ('Arlo AC2001 Chime 2 Wireless Doorbell', 'video doorbell', False),
    ('eufy Video Doorbell Add-On Chime', 'video doorbell', False),
    ('Arlo AVD4001 Video Doorbell with Chime', 'video doorbell', True),
    ('Inkbird Slow Cooker Sous Vide ISV-300W', 'slow cooker', False),
    ('Crock-Pot 7 Quart Slow Cooker', 'slow cooker', True),
    ('Oster 220 240 Volt Coffee Maker NOT FOR USA', 'coffee maker', False),
    ('Coffee Maker 120V', 'coffee maker', True),
])
def test_complete_us_product_gate(title, query, expected):
    assert bool(relevant_product(title, query)) == expected


def test_voltage_filter_does_not_reject_a_uk_machine():
    assert relevant_product('Coffee Maker 220 240 Volt', 'coffee maker', 'uk')


def test_component_correction_is_visible_beside_offer_and_repeatable():
    a = {'_generator': {'topic': 'video-doorbells'}, 'content_html':
         '<h3>eufy Doorbell Add-On Chime</h3><a href="/offer">Offer</a>'
         '<h2>How to choose the right option</h2><p>Generic</p><h2>Evidence</h2>'}
    b = enhance_usa_article(a, 'us')
    assert '</h3><p class="wb-component-note"><strong>Add-on indoor chime' in b['content_html']
    assert enhance_usa_article(b, 'us') == b


def test_savvy_angles_answer_different_questions_and_keep_identity():
    results = []
    for angle in ('before-you-shop', 'final-checklist'):
        a = {'slug': f'savvy-buyer-monday-price-comparison-{angle}-us-2026-10-05',
             'title': 'Stable', 'source_sha': 'same', 'content_html': 'Old repeat'}
        b = enhance_savvy_article(a, 'us')
        assert b['title'] == a['title'] and b['source_sha'] == a['source_sha']
        assert enhance_savvy_article(b, 'us') == b
        assert 'Old repeat' not in b['content_html']
        results.append(b['content_html'])
    assert results[0] != results[1]


def test_daily_and_support_generators_keep_editorial_hook():
    from src.search_guides import enhance_search_guide
    a = {'slug': 'stable', '_generator': {'topic': 'blenders'}, 'content_html':
         '<h2>How to choose the right option</h2><p>Generic</p><h2>Evidence</h2>'}
    assert START in enhance_search_guide(a, 'us')['content_html']


def test_event_context_does_not_present_an_old_event_as_current_discount():
    a = {'_generator': {'topic': 'ssds'}, '_event': {'key': 'old-event'}, 'content_html':
         '<h2>How to choose the right option</h2><p>Generic</p><h2>Disclosure</h2>'}
    b = enhance_usa_article(a, 'us')
    assert 'Historical event guide' in b['content_html']
    assert 'does not establish an active event discount today' in b['content_html']
    assert enhance_usa_article(b, 'us') == b
