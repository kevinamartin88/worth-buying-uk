from unittest.mock import Mock
from urllib.parse import quote

import pytest

from src.cfs_prices import price_from_cfs_page
from src.rakuten import RakutenProduct
from generate_rakuten_articles import validated_products
from refresh_cfs_prices import refresh_content
from datetime import datetime, timezone

URL = "https://www.choicefurnituresuperstore.co.uk/p/example-wardrobe"


def page(current="149.00", currency="GBP", meta="149.00", url=URL):
    return f'''<input name="price" value="199.00"><div id="hideprice"><div class="price">
    <span class="pStroke">&pound;199.00</span><span class="pOne red">&pound;{current}</span></div>
    <p itemprop="offers"><link itemprop="url" href="{url}"><meta itemprop="priceCurrency" content="{currency}">
    <meta itemprop="price" content="{meta}"></p></div>
    <div><span class="pOne">&pound;9.99</span><meta itemprop="price" content="9.99"></div>'''


def test_uses_primary_current_price_not_rrp_hidden_cart_or_related_item():
    assert price_from_cfs_page(page(), URL) == "149.00"


@pytest.mark.parametrize('document', [page(currency="USD"), page(meta="199.00"), page(url=URL + "-different"), page(current="NaN"), '<span class="pStroke">£199</span>', page().replace('id="hideprice"', 'id="related"')])
def test_ambiguous_missing_or_foreign_price_is_never_guessed(document):
    assert price_from_cfs_page(document, URL) is None


@pytest.mark.parametrize('document,expected', [(page(), '149.00'), ('<p>Unverified price</p>', '')])
def test_generator_replaces_cfs_feed_rrp_or_suppresses_unverified_price(document, expected):
    product = RakutenProduct('Example Wardrobe', 'Choice Furniture Superstore', 'https://click.linksynergy.com/link?murl=' + quote(URL, safe=''), '199.00', 'GBP')
    client = Mock()
    client.validate_product_destination.return_value = (True, 'ok', URL)
    client._validated_product_pages = {product.url: (document, URL)}
    assert validated_products(client, [product], 'uk')[0].price == expected


@pytest.mark.parametrize('verified,expected', [(True, '£149.00'), (False, 'Check the current retailer price')])
def test_refreshes_old_cfs_quote_without_changing_other_offers(verified, expected):
    tracking = 'https://click.linksynergy.com/link?murl=' + quote(URL, safe='')
    content = f'<p>Intro</p><h2>Offers</h2><h3>1. Example Wardrobe</h3><p><strong>Price when checked:</strong> £199.00.</p><p><a href="{tracking}">Buy</a></p><h3>2. Other retailer</h3><p><strong>Price when checked:</strong> £88.00.</p><h2>Advice</h2>'
    client = Mock()
    client.validate_product_destination.return_value = (verified, 'ok', URL)
    client._validated_product_pages = {tracking: (page(), URL)}
    result, count, verified_count = refresh_content(content, client, datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert count == 1 and verified_count == int(verified)
    assert expected in result and '£199.00' not in result
    assert '£88.00' in result and tracking in result
    again, _, _ = refresh_content(result, client, datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert again == result
