import copy
import html
from urllib.parse import parse_qs, urlsplit

import pytest

from src.publication_quality import choose_description, repair_affiliate_links, affiliate_issues, CONFIG
from src.publishing_seo import repair_metadata, enrich_metadata, metadata_html
from verify_publication import assess, verify_one


def test_render_probe_uses_reader_url_without_cache_busting(monkeypatch):
    from unittest.mock import Mock
    import verify_publication as verification
    browser = Mock()
    context = browser.new_context.return_value
    page = context.new_page.return_value
    url = 'https://www.worthbuyinguk.co.uk/2026/11/guide.html'
    page.url = url
    page.goto.return_value.status = 200
    monkeypatch.setattr(verification, 'assess', lambda *args: {'verification': 'passed'})
    assert verification.render_probe(browser, {}, 'uk', url)['verification'] == 'passed'
    page.goto.assert_called_once_with(url, wait_until='domcontentloaded', timeout=20000)
    context.close.assert_called_once()


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


def test_indistinguishable_guides_are_flagged_instead_of_inventing_different_claims(monkeypatch):
    import verify_publication
    row = article()
    monkeypatch.setattr(verify_publication, 'description_conflicts', lambda *args: ['duplicate-guide'])
    data = observed(row)
    result = assess(data, row, 'uk', data['canonical'])
    assert result['verification'] == 'needs_attention'
    assert any('editorial review' in issue for issue in result['issues'])


@pytest.mark.parametrize('market',['uk','us'])
@pytest.mark.parametrize('query,bad',[
    ('streaming devices','USB Power Cable Adapter for Fire TV Stick'),
    ('food processors','KitchenAid Food Processor Attachment'),
    ('air purifiers','HEPA Filter for Basement Air Purifier'),
    ('wireless earbuds','Foldable Wireless Charging Stand'),
    ('video doorbells','eufy Video Doorbell Add-On Chime'),
    ('hair straighteners','Dyson Corrale Hair Straightener Power Supply Charging Cable'),
])
def test_product_backstop_returns_publishable_guidance_without_bad_offers(query,bad,market):
    from src.product_checks import prepare_article_products
    row={'slug':'stable-guide','title':'4 Best Products from $13','mode':'publish',
         'content_html':f'<h3>1. {bad}</h3><p><a rel="sponsored nofollow" href="https://www.ebay.com/itm/123">View offer</a></p>',
         '_generator':{'query':query,'pick_count':4,'live_ebay_picks':True},
         '_promotion':{'promotion_token':'same-token','daily_featured_date':'2026-11-20'}}
    before=copy.deepcopy(row)
    result=prepare_article_products(row,market)
    assert row==before
    assert result['mode']=='publish' and result['slug']==row['slug']
    assert result['_promotion']==row['_promotion']
    assert result['_generator']['pick_count']==0
    assert bad not in result['content_html'] and '/itm/123' not in result['content_html']
    assert 'links open searches' in result['content_html']
    assert result['_seo']['description'] and '4 Best Products' not in result['title']
    assert prepare_article_products(result,market) is result
    assert ('worthbuyin008-21' if market=='uk' else 'worthbuyingus-20') in result['content_html']


def test_good_articles_keep_the_same_body_metadata_and_fingerprint():
    from pathlib import Path
    import json
    from src.product_checks import prepare_article_products
    root=Path(__file__).resolve().parents[1]
    for market,folder in [('uk','articles'),('us','articles-us')]:
        for path in (root/folder).glob('*.json'):
            row=json.loads(path.read_text(encoding='utf8'))
            assert prepare_article_products(row,market) is row, str(path)


def test_optional_markup_inspection_error_falls_back_instead_of_stopping(monkeypatch):
    from src import product_checks
    def unavailable(*args):raise ValueError('unexpected markup')
    monkeypatch.setattr(product_checks.RecommendationTitles,'feed',unavailable)
    result=product_checks.prepare_article_products({'slug':'x','title':'Guide','mode':'publish','content_html':'<p>Original</p>'},'uk')
    assert result['mode']=='publish' and result['_product_checks']['outcome']=='buying-guide-fallback'


def test_retailer_only_roundup_fallback_does_not_switch_affiliate_networks():
    from src.product_checks import prepare_article_products
    row={'title':'Air purifier offers','_generator':{'channel':'rakuten','query':'air purifier'},'content_html':'<h3>1. HEPA Filter for Air Purifier</h3><a rel="sponsored" href="https://click.linksynergy.com/x">Offer</a>'}
    result=prepare_article_products(row,'us')
    assert 'amazon.' not in result['content_html'] and 'ebay.' not in result['content_html']
    assert result['_generator']['pick_count']==0


def test_amazon_event_selection_uses_the_actual_uk_market(monkeypatch):
    import generate_prime_big_deal_articles as prime
    from types import SimpleNamespace
    offers=[SimpleNamespace(title='TP Link Smart Wi-Fi Plug HS100 EU PLUG',image_url='https://example.com/eu.jpg')]
    offers += [SimpleNamespace(title=f'Tapo Smart Plug P110 UK {i}',image_url='https://example.com/uk.jpg') for i in range(3)]
    class Client:
        def search_offers(self,*args,**kwargs):return offers
    monkeypatch.setattr(prime.AmazonCreatorsClient,'from_env',lambda market:Client())
    selected=prime._amazon_prime_offers(prime.topic_by_key('smart-plugs'),'uk')
    assert len(selected)==3 and all('EU PLUG' not in x.title for x in selected)


@pytest.mark.parametrize('market,marketplace',[('uk','EBAY_GB'),('us','EBAY_US')])
def test_older_niche_route_writes_useful_tracked_fallback_when_all_offers_fail(monkeypatch,tmp_path,market,marketplace):
    import main as niche
    cfg={'site':{'marketplace':marketplace,'delivery_country':'GB' if market=='uk' else 'US',
                 'title_prefix':'Worth Buying','min_seller_feedback_percent':99,'min_seller_feedback_score':100,'history_max_points_per_item':10},
         'niches':[{'slug':'streaming','name':'Streaming Devices','query':'streaming devices','max_price':250,'min_score':0}],
         'publishing':{'publish_when_no_items':True}}
    class Client:
        def search(self,**kwargs):return [{'title':'USB Power Cable Adapter for Fire TV Stick'}]
    monkeypatch.setattr(niche,'ROOT',tmp_path)
    monkeypatch.setattr(niche,'load_config',lambda:cfg)
    monkeypatch.setattr(niche,'EbayClient',lambda **kwargs:Client())
    monkeypatch.setenv('DRY_RUN','true')
    niche.main()
    content=(tmp_path/'out/streaming.html').read_text(encoding='utf8')
    assert 'USB Power Cable Adapter' not in content
    assert 'links open searches' in content
    assert ('worthbuyin008-21' if market=='uk' else 'worthbuyingus-20') in content
