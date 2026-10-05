from __future__ import annotations

import generate_daily_articles as daily
from src.amazon_creators import AmazonOffer


class FakeAmazonClient:
    def search_offers(self, keywords: str):
        return [
            AmazonOffer(
                title="Ninja Foodi MAX Dual Zone Air Fryer AF400UK",
                price=149.99,
                currency="GBP",
                url="https://www.amazon.co.uk/dp/example",
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
    assert "https://www.amazon.co.uk/dp/example" in section


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
