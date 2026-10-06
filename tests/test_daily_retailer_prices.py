from __future__ import annotations

import generate_daily_articles as daily
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


def test_unverified_air_fryer_has_only_advertised_ebay_product_link():
    item = {
        "title": "11L Double Stack Air Fryer, Family Size Digital with 2x5.5L Baskets Cook",
        "itemWebUrl": "https://www.ebay.co.uk/itm/358703800622",
        "price": {"value": "89.10", "currency": "GBP"},
    }
    for render in (daily.quick_picks_html,
                   lambda rows, market, query: daily.live_sections(rows, market, "Air Fryers", query)):
        content = render([item], "uk", "air fryer")
        assert item["itemWebUrl"] in content
        assert "amazon.co.uk" not in content


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
    assert "amazon.co.uk" not in daily.quick_picks_html([item], "uk", "air fryer")
    assert "amazon.co.uk" not in daily.live_sections([item], "uk", "Air Fryers", "air fryer")


def test_corrected_air_fryer_article_contains_only_direct_product_links():
    import json
    from pathlib import Path
    from html.parser import HTMLParser

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
    assert not any("amazon.co.uk/s?" in url for url in parser.urls)
    assert sum("ebay.co.uk/itm/358703800622" in url for url in parser.urls) == 2
