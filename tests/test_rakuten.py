from __future__ import annotations

import requests
import pytest

from src.rakuten import RakutenClient, RakutenProduct


class FakeResponse:
    def __init__(self, body: str = "", status: int = 200, json_body: dict | None = None):
        self.content = body.encode("utf-8")
        self.status_code = status
        self.json_body = json_body or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self) -> dict:
        return self.json_body


class FakeSession:
    def __init__(self, body: str):
        self.body = body
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(json_body={"access_token": "short-lived-access-token", "expires_in": 3600})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(self.body)


def product_xml(url: str, currency: str = "GBP") -> str:
    return f"""<result><item><mid>53591</mid><merchantname>Samsung UK</merchantname>
    <productname>Example Air Fryer</productname><price currency=\"{currency}\">99.00</price>
    <linkurl>{url.replace('&', '&amp;')}</linkurl></item></result>"""


def test_missing_token_disables_client(monkeypatch):
    for market in ("UK", "US"):
        monkeypatch.delenv(f"RAKUTEN_{market}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"RAKUTEN_{market}_CLIENT_SECRET", raising=False)
        monkeypatch.delenv(f"RAKUTEN_{market}_ACCOUNT_ID", raising=False)
    assert RakutenClient.for_market("uk") is None
    assert RakutenClient.for_market("us") is None


def test_returns_valid_uk_tracking_product_without_leaking_token():
    session = FakeSession(product_xml("https://click.linksynergy.com/deeplink?id=abc&mid=53591"))
    client = RakutenClient("client-id", "super-secret", "uk-account", "GBP", session=session)

    product = client.search_one("air fryers")

    assert product is not None
    assert product.merchant == "Samsung UK"
    assert product.currency == "GBP"
    token_call, search_call = session.calls
    assert token_call[0] == "POST"
    assert token_call[2]["data"] == {"grant_type": "password", "scope": "uk-account"}
    assert "super-secret" not in str(token_call[2]["data"])
    assert search_call[0] == "GET"
    assert search_call[2]["headers"] == {"Authorization": "Bearer short-lived-access-token"}
    assert "super-secret" not in str(search_call[2]["params"])


def test_rejects_untrusted_or_foreign_currency_links():
    untrusted = RakutenClient(
        "id", "secret", "account", "GBP", session=FakeSession(product_xml("https://example.com/product"))
    )
    foreign = RakutenClient(
        "id",
        "secret",
        "account",
        "GBP",
        session=FakeSession(product_xml("https://click.linksynergy.com/deeplink?id=abc", "USD")),
    )

    assert untrusted.search_one("air fryers") is None
    assert foreign.search_one("air fryers") is None


def test_usa_client_accepts_usd(monkeypatch):
    monkeypatch.setenv("RAKUTEN_US_CLIENT_ID", "usa-client")
    monkeypatch.setenv("RAKUTEN_US_CLIENT_SECRET", "usa-secret")
    monkeypatch.setenv("RAKUTEN_US_ACCOUNT_ID", "usa-account")
    session = FakeSession(product_xml("https://click.linksynergy.com/deeplink?id=usa", "USD"))

    client = RakutenClient.for_market("us", session=session)

    assert client is not None
    assert client.search_one("air fryer") is not None


def test_search_returns_unique_products():
    duplicate_items = (
        product_xml("https://click.linksynergy.com/deeplink?id=abc&mid=53591")
        .replace("<result>", "")
        .replace("</result>", "")
    )
    session = FakeSession(f"<result>{duplicate_items}{duplicate_items}</result>")
    client = RakutenClient("client-id", "super-secret", "uk-account", "GBP", session=session)

    products = client.search("air fryers", limit=5)

    assert len(products) == 1
    assert products[0].name == "Example Air Fryer"


def test_coupon_feed_returns_code_and_no_code_offers():
    body = """<couponfeed><link>
      <advertiserid>53731</advertiserid><advertisername>Example UK</advertisername>
      <offerdescription>Save 20% on selected home products</offerdescription>
      <couponcode>HOME20</couponcode><couponrestriction>Selected products only</couponrestriction>
      <offerstartdate>2026-09-01</offerstartdate><offerenddate>2026-10-31</offerenddate>
      <clickurl>https://click.linksynergy.com/deeplink?id=abc&amp;mid=53731</clickurl>
      <categories><category>Home</category></categories>
      <promotiontypes><promotiontype>Coupon Code</promotiontype></promotiontypes>
    </link><link>
      <advertiserid>52994</advertiserid><advertisername>Second Shop</advertisername>
      <offerdescription>Free delivery this week</offerdescription><couponcode>N/A</couponcode>
      <clickurl>https://click.linksynergy.com/deeplink?id=def&amp;mid=52994</clickurl>
    </link></couponfeed>"""
    session = FakeSession(body)
    client = RakutenClient("client-id", "super-secret", "uk-account", "GBP", session=session)

    offers = client.coupons(network=3, limit=100)

    assert len(offers) == 2
    assert offers[0].code == "HOME20"
    assert offers[0].categories == ("Home",)
    assert offers[0].promotion_types == ("Coupon Code",)
    assert offers[1].code == ""
    coupon_call = session.calls[1]
    assert coupon_call[2]["params"] == {"network": 3, "resultsperpage": 100, "pagenumber": 1}
    assert "super-secret" not in str(coupon_call)


def test_coupon_feed_rejects_untrusted_links_and_invalid_network():
    body = """<couponfeed><link><advertisername>Bad Shop</advertisername>
      <offerdescription>Suspicious offer</offerdescription>
      <clickurl>https://example.com/not-rakuten</clickurl></link></couponfeed>"""
    client = RakutenClient("id", "secret", "account", "GBP", session=FakeSession(body))

    assert client.coupons(network=3) == []
    with pytest.raises(ValueError, match="network"):
        client.coupons(network=2)


class DestinationResponse(FakeResponse):
    def __init__(
        self,
        body: str,
        final_url: str,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ):
        super().__init__(body=body, status=status)
        self.url = final_url
        self.headers = {"Content-Type": content_type}
        self.text = body


class DestinationSession:
    def __init__(self, response: DestinationResponse):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.response


def rakuten_product(name: str, destination: str) -> RakutenProduct:
    from urllib.parse import quote

    return RakutenProduct(
        name=name,
        merchant="Sharper Image",
        url=(
            "https://click.linksynergy.com/link?id=test&type=15&murl="
            + quote(destination, safe="")
        ),
        price="79.99",
        currency="USD",
    )


def test_validates_matching_retailer_product_page_without_clicking_affiliate_link():
    destination = "https://sharperimage.com/products/star-wars-5-quart-slow-cooker"
    response = DestinationResponse(
        "<html><head><title>Star Wars 5-Quart Slow Cooker | Sharper Image</title></head>"
        "<body><h1>Star Wars 5-Quart Slow Cooker</h1><p>5-quart slow cooker.</p></body></html>",
        destination,
    )
    session = DestinationSession(response)
    client = RakutenClient("id", "secret", "account", "USD", session=session)

    ok, reason, final_url = client.validate_product_destination(
        rakuten_product("Star Wars 5-Quart Slow Cooker", destination)
    )

    assert ok is True
    assert reason == "validated retailer product page"
    assert final_url == destination
    assert session.calls[0][1] == destination
    assert "click.linksynergy.com" not in session.calls[0][1]


def test_rejects_soft_404_even_when_http_status_is_200():
    destination = "https://sharperimage.com/products/mickey-mouse-and-minnie-mouse-5-quart-slow-cooker"
    response = DestinationResponse(
        "<html><head><title>Page Not Found | Sharper Image</title></head>"
        "<body>The page you requested could not be found.</body></html>",
        "https://sharperimage.com/404",
    )
    client = RakutenClient("id", "secret", "account", "USD", session=DestinationSession(response))

    ok, reason, _ = client.validate_product_destination(
        rakuten_product("Mickey Mouse and Minnie Mouse 5-Quart Slow Cooker", destination)
    )

    assert ok is False
    assert "generic or error page" in reason or "soft 404" in reason


def test_rejects_page_that_does_not_match_feed_product_name():
    destination = "https://sharperimage.com/products/star-wars-5-quart-slow-cooker"
    response = DestinationResponse(
        "<html><head><title>Sharper Image | Innovative Gifts</title></head>"
        "<body><h1>Best Sellers</h1><p>Massage chairs and travel accessories.</p></body></html>",
        destination,
    )
    client = RakutenClient("id", "secret", "account", "USD", session=DestinationSession(response))

    ok, reason, _ = client.validate_product_destination(
        rakuten_product("Star Wars 5-Quart Slow Cooker", destination)
    )

    assert ok is False
    assert "does not match product title" in reason


def test_rejects_affiliate_link_without_inspectable_product_destination():
    product = RakutenProduct(
        name="Example Product",
        merchant="Example",
        url="https://click.linksynergy.com/deeplink?id=abc&mid=123",
        price="10",
        currency="USD",
    )
    client = RakutenClient(
        "id",
        "secret",
        "account",
        "USD",
        session=DestinationSession(
            DestinationResponse("<html></html>", "https://example.com/product")
        ),
    )

    ok, reason, final_url = client.validate_product_destination(product)

    assert ok is False
    assert "no inspectable retailer murl" in reason
    assert final_url == ""
