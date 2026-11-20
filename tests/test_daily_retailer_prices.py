from __future__ import annotations

import generate_daily_articles as daily
import json
from pathlib import Path
from src.product_relevance import streaming_player
from src.uk_editorial import relevant_uk_product
from src.usa_conversion import relevant_product

import pytest
from src.amazon_creators import AmazonOffer


class FakeAmazonClient:
    def search_offers(self, keywords: str):
        return [
            AmazonOffer(
                title="Ninja Foodi MAX Dual Zone Air Fryer AF400UK",
                price=149.99,
                currency="GBP",
                url="https://www.amazon.co.uk/dp/B0EXAMPLE1",
            )
        ]


def test_exact_model_adds_amazon_price_to_article_and_short_copy(monkeypatch):
    item = {
        "title": "Ninja AF400UK Air Fryer New With Tags",
        "condition": "New with tags",
        "price": {"value": "129.99", "currency": "GBP"},
        "itemWebUrl": "https://www.ebay.co.uk/itm/example",
        "seller": {"feedbackPercentage": "99.9", "feedbackScore": 400},
    }
    monkeypatch.setattr(
        daily.AmazonCreatorsClient,
        "from_env",
        classmethod(lambda cls, market: FakeAmazonClient()),
    )

    daily.add_amazon_prices([item], "uk", "air fryer")
    section = daily.live_sections([item], "uk", "Air Fryers", "air fryer")

    assert "eBay £129.99; Amazon £149.99" in section
    assert "https://www.amazon.co.uk/dp/B0EXAMPLE1" in section


def test_generic_listing_does_not_claim_an_unverified_amazon_price(monkeypatch):
    item = {
        "title": "Large Family Air Fryer New",
        "condition": "New",
        "price": {"value": "59.99", "currency": "GBP"},
    }
    monkeypatch.setattr(
        daily.AmazonCreatorsClient,
        "from_env",
        classmethod(lambda cls, market: FakeAmazonClient()),
    )

    daily.add_amazon_prices([item], "uk", "air fryer")

    assert "_amazon_offer" not in item


def test_refurbished_query_requires_verified_refurbished_condition():
    item = {
        "title": "Ninja AF400UK Large Capacity Air Fryer",
        "condition": "Certified - Refurbished",
        "price": {"value": "100", "currency": "GBP"},
        "image": {"imageUrl": "https://example.com/product.jpg"},
        "seller": {"feedbackPercentage": "99.9", "feedbackScore": 1000},
    }
    query = "refurbished large capacity air fryer"
    assert daily.listing_score(item, 400, "GBP", query=query) is not None
    for condition in ("New", "New other (see details)", "Used", ""):
        item["condition"] = condition
        assert daily.listing_score(item, 400, "GBP", query=query) is None


@pytest.mark.parametrize("title", [
    "11L Double Stack Air Fryer, Family Size Digital with 2x5.5L Baskets Cook",
    "VonShef Air Fryer 6L - Large Family Size, 10-in-1, Healthy Cooking",
    "Air Fryer 2x5.5L 2400W Digital",
])
def test_capacity_and_feature_counts_are_not_models(title):
    query, exact = daily.amazon_model_query(title, "air fryer")
    assert exact is False
    assert "Air Fryer" in query


def test_unverified_air_fryer_keeps_ebay_and_adds_amazon_search_alternative():
    item = {
        "title": "11L Double Stack Air Fryer, Family Size Digital with 2x5.5L Baskets Cook",
        "itemWebUrl": "https://www.ebay.co.uk/itm/358703800622",
        "price": {"value": "89.10", "currency": "GBP"},
    }
    for render in (daily.quick_picks_html,
                   lambda rows, market, query: daily.live_sections(rows, market, "Air Fryers", query)):
        content = render([item], "uk", "air fryer")
        assert item["itemWebUrl"] in content
        assert "amazon.co.uk/s?" in content
        assert "tag=worthbuyin008-21" in content
        assert "Search Amazon UK" in content


@pytest.mark.parametrize("changes", [
    {"title": "Other AF400UK Storage Boxes"},
    {"title": "Ninja AF400UK Storage Boxes"},
    {"title": "Ninja AF400UK Air Fryer Replacement Basket Only"},
    {"title": "Ninja AF400UKXL Air Fryer"},
    {"url": "https://www.amazon.co.uk/s?k=Ninja+AF400UK"},
    {"url": "https://www.amazon.co.uk.evil.example/dp/B0EXAMPLE1"},
    {"currency": "USD"},
    {"price": float("nan")},
])
def test_wrong_product_or_unverified_destination_is_not_rendered(changes):
    item = {
        "title": "Ninja AF400UK Air Fryer",
        "itemWebUrl": "https://www.ebay.co.uk/itm/example",
        "price": {"value": "129.99", "currency": "GBP"},
        "_amazon_offer": {
            "title": "Ninja AF400UK Air Fryer", "price": 149.99, "currency": "GBP",
            "url": "https://www.amazon.co.uk/dp/B0EXAMPLE1", **changes,
        },
    }
    quick = daily.quick_picks_html([item], "uk", "air fryer")
    detail = daily.live_sections([item], "uk", "Air Fryers", "air fryer")
    for content in (quick, detail):
        assert "amazon.co.uk/s?" in content
        assert "tag=worthbuyin008-21" in content
        assert "amazon.co.uk/dp/B0EXAMPLE1" not in content


def test_corrected_air_fryer_article_uses_valid_retailer_links_for_its_mode():
    import json
    from pathlib import Path
    from html.parser import HTMLParser
    from urllib.parse import urlsplit

    class Links(HTMLParser):
        urls = None

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.urls.append(dict(attrs).get("href", ""))

    path = Path(daily.ROOT) / "articles/best-large-capacity-air-fryers-worth-buying-uk.json"
    article = json.loads(path.read_text(encoding="utf-8"))
    parser = Links()
    parser.urls = []
    parser.feed(article["content_html"])

    retailer_mode = str((article.get("_monetisation") or {}).get("retailer_mode") or "")
    event_key = str((article.get("_event") or {}).get("key") or "")
    is_prime_amazon_only = (
        retailer_mode == "amazon-only"
        or event_key == "prime-big-deal-days-2026"
    )

    if is_prime_amazon_only:
        retailer_urls = [
            url for url in parser.urls
            if "amazon.co.uk" in url or "ebay.co.uk" in url
        ]
        assert retailer_urls
        assert not any("ebay.co.uk" in url for url in retailer_urls)
        assert all(
            (urlsplit(url).hostname or "").casefold()
            in {"amazon.co.uk", "www.amazon.co.uk"}
            for url in retailer_urls
        )
        return

    # Evergreen/non-event articles must still avoid generic Amazon search fallbacks
    # and keep the known direct eBay product link used by this regression fixture.
    assert not any("amazon.co.uk/s?" in url for url in parser.urls)
    assert sum("ebay.co.uk/itm/358703800622" in url for url in parser.urls) == 2


def test_colour_only_product_variants_share_one_fingerprint():
    black = daily.listing_variant_fingerprint(
        "Dyson V15 Detect Cordless Vacuum Cleaner - Black",
        "cordless vacuum cleaner",
    )
    blue = daily.listing_variant_fingerprint(
        "Dyson V15 Detect Cordless Vacuum Cleaner - Blue",
        "cordless vacuum cleaner",
    )
    assert black == blue


def test_colour_word_in_actual_query_is_not_discarded():
    white = daily.listing_variant_fingerprint(
        "Portable White Noise Machine with Night Light",
        "white noise machine",
    )
    black = daily.listing_variant_fingerprint(
        "Portable Black Noise Machine with Night Light",
        "white noise machine",
    )
    assert white != black


def test_smartwatch_variety_prefers_apple_and_distinct_models():
    rows = [
        {"title": "Samsung Galaxy Watch 6 40mm Bluetooth Smartwatch Black"},
        {"title": "Samsung Galaxy Watch 6 40mm Bluetooth Smartwatch Silver"},
        {"title": "Samsung Galaxy Watch5 40mm GPS Smartwatch Rose Gold"},
        {"title": "Apple Watch Series 6 40mm Smartwatch Black"},
        {"title": "Amazfit Active 2 GPS Smartwatch Black"},
        {"title": "Garmin Venu 3 GPS Smartwatch Black"},
    ]

    selected = daily.diversify_smartwatch_picks(rows, "smartwatch", limit=4)
    titles = [row["title"] for row in selected]

    assert any(title.startswith("Apple Watch") for title in titles)
    assert sum("Galaxy Watch 6" in title for title in titles) == 1
    assert sum(title.startswith("Samsung") for title in titles) <= 2
    assert len({daily._smartwatch_brand(title) for title in titles}) >= 3


def test_asin_identity_is_used_as_strongest_amazon_match(monkeypatch):
    item = {
        "title": "Ninja Dual Zone Air Fryer",
        "condition": "New",
        "price": {"value": "129.99", "currency": "GBP"},
        "localizedAspects": [
            {"name": "Brand", "value": "Ninja"},
            {"name": "ASIN", "value": "B0ABCDEF12"},
        ],
    }

    class AsinClient:
        def __init__(self):
            self.queries = []
        def search_offers(self, keywords: str):
            self.queries.append(keywords)
            return [
                AmazonOffer(
                    title="Ninja Dual Zone Air Fryer",
                    price=149.99,
                    currency="GBP",
                    url="https://www.amazon.co.uk/dp/B0ABCDEF12",
                    asin="B0ABCDEF12",
                    brand="Ninja",
                )
            ]

    client = AsinClient()
    monkeypatch.setattr(
        daily.AmazonCreatorsClient,
        "from_env",
        classmethod(lambda cls, market: client),
    )

    daily.add_amazon_prices([item], "uk", "air fryer")

    assert client.queries[0] == "B0ABCDEF12"
    assert item["_amazon_offer"]["asin"] == "B0ABCDEF12"
    rendered = daily.quick_picks_html([item], "uk", "air fryer")
    assert "Check exact match on Amazon UK" in rendered
    assert "amazon.co.uk/dp/B0ABCDEF12" in rendered



# Streaming players must not be confused with their compatible accessories.
QUERY='Fire TV Roku streaming device'
BAD=[
    '2Pcs Usb Power Cord Compatible With Fire Tv Stick,roku Streaming Stick',
    'One For All 5 Device Backlit URC7945 Smart Streamer Remote',
    'Roku Streaming Stick remote control',
    'Voice Remote for Roku Streaming Stick 4K 3820RW',
    'USB Power Adapter for Amazon Fire TV Stick 4K',
    'Roku Streaming Stick 4K replacement receiver cable',
    'Silicone Case for Fire TV Stick Voice Remote',
    'HDMI Extender Compatible With Roku Streaming Stick',
    'Roku Streaming Stick 4K device cable only',
    'Roku Streaming Stick 4K for parts not working',
]
GOOD=[
    'Roku Streaming Stick 4K Device 4K HDR Dolby Vision Voice Remote - 3820RW',
    'Roku Streaming Stick Plus 4K HDR Media Player with Voice Remote - 3810R',
    'Roku Streaming Stick 4K with remote control and USB power cable',
    'Amazon Fire TV Stick 4K Max with Alexa Voice Remote and power adapter',
    'Google Chromecast with Google TV 4K',
    'Apple TV 4K 64GB A2169 with Siri Remote',
    'NVIDIA SHIELD TV Pro 4K HDR Streaming Media Player',
    'onn. Google TV 4K Streaming Box with remote',
]
def listing(title,market,item_id='example'):
    return {'itemId':item_id,'title':title,'condition':'New','price':{'value':'29.99','currency':'USD' if market=='us' else 'GBP'},'image':{'imageUrl':'https://example.com/player.jpg'},'seller':{'feedbackPercentage':'99.8','feedbackScore':1000},'buyingOptions':['FIXED_PRICE'],'itemWebUrl':f'https://www.ebay.com/itm/{item_id}','listingMarketplaceId':'EBAY_US','itemLocation':{'country':'US'},'estimatedAvailabilities':[{'estimatedAvailabilityStatus':'IN_STOCK','estimatedAvailableQuantity':1}]}

@pytest.mark.parametrize('title',BAD)
@pytest.mark.parametrize('market',['uk','us'])
def test_accessories_cannot_enter_either_market_shortlist(title,market):
    assert not streaming_player(title)
    assert not relevant_product(title,QUERY,market)
    assert not relevant_uk_product(title,QUERY)
    assert daily.listing_score(listing(title,market),250,'USD' if market=='us' else 'GBP',QUERY) is None

@pytest.mark.parametrize('title',GOOD)
@pytest.mark.parametrize('market',['uk','us'])
def test_complete_players_keep_their_bundled_remote_and_power_equipment(title,market):
    assert streaming_player(title)
    assert relevant_product(title,QUERY,market)
    assert relevant_uk_product(title,QUERY)
    assert daily.listing_score(listing(title,market),250,'USD' if market=='us' else 'GBP',QUERY) is not None

@pytest.mark.parametrize('market',['uk','us'])
@pytest.mark.parametrize('item_type',['Remote Control','Charging Adapter','USB Power Cord'])
def test_contradictory_retailer_type_is_rejected(market,item_type):
    item=listing(GOOD[0],market)
    item['localizedAspects']=[{'name':'Type','value':item_type}]
    assert daily.listing_score(item,250,item['price']['currency'],QUERY) is None

@pytest.mark.parametrize('market',['uk','us'])
def test_accessory_only_results_still_build_the_normal_fallback(monkeypatch,tmp_path,market):
    class Client:
        def search(self,**kwargs):return [listing(title,market,str(i)) for i,title in enumerate(BAD)]
        def get_item(self,*args,**kwargs):raise AssertionError('Rejected accessories must never be fetched as picks')
    monkeypatch.setattr(daily.EbayClient,'for_market',lambda market:Client())
    monkeypatch.setattr(daily,'_record_price_history',lambda *args:None)
    monkeypatch.setattr(daily,'ROOT',tmp_path)
    topic=next(t for t in daily.TOPICS if t[0]=='streaming-devices')
    article=daily.build_article(topic,market,2026)
    assert article['mode']=='publish'
    assert article['_generator']['live_ebay_picks'] is False
    assert article['_generator']['pick_count']==0
    assert 'Popular current listings' in article['content_html']
    assert not any(title in article['content_html'] for title in BAD)

def test_repaired_existing_guide_has_two_actual_players_and_keeps_its_slug():
    path=Path(__file__).resolve().parents[1]/'articles-us/best-streaming-devices-worth-buying-us.json'
    article=json.loads(path.read_text(encoding='utf-8'))
    content=article['content_html']
    assert article['slug']=='best-streaming-devices-worth-buying-us'
    assert article['_research']['models_compared']==2
    assert content.count('data-wb-product=')==2
    assert 'URC7945' not in content and '2Pcs' not in content
    assert 'Best overall' not in content and 'WorthBuying score' not in content
    assert '$13.39' not in content and '$33' not in article['title']
    assert 'tag=worthbuyingus-20' in content and 'campid=5339209205' in content
    assert 'developer.roku.com/dev/docs/hardware' in content

def test_repaired_uk_guide_uses_uk_affiliate_tags_and_no_accessory_picks():
    path=Path(__file__).resolve().parents[1]/'articles/best-streaming-devices-worth-buying-uk.json'
    article=json.loads(path.read_text(encoding='utf-8'))
    content=article['content_html']
    assert article['slug']=='best-streaming-devices-worth-buying-uk'
    assert article['_research']['models_compared']==2
    assert content.count('data-wb-product=')==2
    assert 'One For All' not in content and 'RCA Converter' not in content
    assert 'tag=worthbuyin008-21' in content and 'campid=5339209132' in content
    assert 'worthbuyingus-20' not in content and '5339209205' not in content
    assert 'www.worthbuyingusa.com' not in content
