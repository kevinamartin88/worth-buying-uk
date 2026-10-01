from __future__ import annotations

from datetime import datetime, timezone

import generate_rakuten_articles as generator
from src.rakuten import RakutenProduct


def products(count: int = 3) -> list[RakutenProduct]:
    return [
        RakutenProduct(
            name=f"Example Air Fryer {index}",
            merchant="Example Retailer",
            url=f"https://click.linksynergy.com/deeplink?id={index}&mid=123",
            price=f"{89 + index}.00",
            currency="GBP",
            advertiser_id="123",
        )
        for index in range(1, count + 1)
    ]


def test_builds_a_separate_rakuten_only_article():
    topic = next(topic for topic in generator.TOPICS if topic[0] == "air-fryers")
    article = generator.build_article(
        topic,
        products(),
        "uk",
        datetime(2026, 9, 28, tzinfo=timezone.utc),
    )

    assert article["_generator"]["channel"] == "rakuten"
    assert article["_generator"]["offer_count"] == 3
    assert article["content_html"].count('rel="sponsored nofollow"') == 3
    assert "amazon.co" not in article["content_html"].casefold()
    assert "ebay.co" not in article["content_html"].casefold()
    assert "separate Rakuten Advertising retailer roundup" in article["content_html"]
    assert article["mode"] == "publish"


def test_relevance_gate_removes_unrelated_feed_results():
    feed = products(3) + [
        RakutenProduct(
            name="Unrelated Television",
            merchant="Example Retailer",
            url="https://click.linksynergy.com/deeplink?id=tv",
            currency="GBP",
        )
    ]

    matches = generator.relevant_products(feed, "air fryer")

    assert len(matches) == 3
    assert all("Air Fryer" in product.name for product in matches)


class FakeClient:
    def __init__(self, results: list[RakutenProduct]):
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 5) -> list[RakutenProduct]:
        self.queries.append(query)
        return self.results[:limit]


def test_offer_gate_requires_three_relevant_products():
    client = FakeClient(products(2))

    topic, matches = generator.find_offer_set(client, 9, [])

    assert topic is None
    assert matches == []
    assert len(client.queries) <= generator.MAX_SEARCHES_PER_MARKET


def test_sharper_image_is_prioritized_for_usa_roundups():
    offers = products(5) + [
        RakutenProduct(
            name="Example Air Fryer Sharper",
            merchant="Sharper Image",
            url="https://click.linksynergy.com/deeplink?id=sharper&mid=456",
            price="129.00",
            currency="USD",
            advertiser_id="456",
        )
    ]

    ranked = generator.prioritize_products(offers, "us")

    assert ranked[0].merchant == "Sharper Image"
    assert len(ranked[: generator.MAX_PRODUCTS]) == generator.MAX_PRODUCTS


def test_single_sharper_image_roundup_adds_title_image_branding():
    topic = next(topic for topic in generator.TOPICS if topic[0] == "dehumidifiers")
    offers = [
        RakutenProduct(
            name=f"Sharper Image Dehumidifier {index}",
            merchant="Sharper Image",
            url=f"https://click.linksynergy.com/deeplink?id={index}&mid=456",
            price="129.00",
            currency="USD",
            advertiser_id="456",
        )
        for index in range(1, 4)
    ]

    article = generator.build_article(
        topic,
        offers,
        "us",
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )

    assert article["featured_retailer"] == "Sharper Image"
    assert article["retailer_logo_asset"] == "assets/retailers/sharper-image.svg"
    assert article["_generator"]["featured_retailer"] == "Sharper Image"
