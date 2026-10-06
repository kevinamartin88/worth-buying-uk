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


def test_choice_furniture_is_prioritized_for_uk_roundups():
    offers = products(5) + [
        RakutenProduct(
            name="Oak Dining Table",
            merchant="Choice Furniture Superstore",
            url="https://click.linksynergy.com/deeplink?id=choice&mid=789",
            price="599.00",
            currency="GBP",
            advertiser_id="789",
        )
    ]

    ranked = generator.prioritize_products(offers, "uk")

    assert ranked[0].merchant == "Choice Furniture Superstore"
    assert len(ranked[: generator.MAX_PRODUCTS]) == generator.MAX_PRODUCTS


def test_choice_furniture_topics_are_searched_first_for_uk():
    topics = generator.candidate_topics(10, [], "uk")

    assert [topic[0] for topic in topics[:5]] == [
        "dining-tables",
        "coffee-tables",
        "bed-frames",
        "wardrobes",
        "sideboards",
    ]


def test_truncated_choice_furniture_name_is_displayed_in_full():
    topic = next(topic for topic in generator.RAKUTEN_TOPICS if topic[0] == "dining-tables")
    offers = [
        RakutenProduct(
            name=f"Oak Dining Table {index}",
            merchant="Choice Furniture Supersto",
            url=f"https://click.linksynergy.com/deeplink?id={index}&mid=789",
            price="599.00",
            currency="GBP",
            advertiser_id="789",
        )
        for index in range(1, 4)
    ]

    article = generator.build_article(
        topic,
        offers,
        "uk",
        datetime(2026, 10, 2, tzinfo=timezone.utc),
    )

    assert article["featured_retailer"] == "Choice Furniture Superstore"
    assert "Choice Furniture Superstore" in article["content_html"]
    assert "Choice Furniture Supersto (Ad)" not in article["content_html"]


def test_single_sharper_image_roundup_adds_title_image_branding():
    topic = next(topic for topic in generator.TOPICS if topic[0] == "dehumidifiers")
    offers = [
        RakutenProduct(
            name=f"Sharper Image Dehumidifier {index}",
            merchant="Sharper Image",
            url=f"https://click.linksynergy.com/deeplink?id={index}&mid=456&murl=https%3A%2F%2Fwww.sharperimage.com%2Fp%2Fdehumidifier-{index}",
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

def test_wardrobe_gate_rejects_hanging_rails_and_accessories():
    feed = [
        RakutenProduct(
            name="Rauch Orange Compartment Hanging Rail 90cm For Sliding Wardrobe",
            merchant="Choice Furniture Superstore",
            url="https://click.linksynergy.com/deeplink?id=rail",
            price="39.95",
            currency="GBP",
        ),
        RakutenProduct(
            name="Rauch 2 Door Sliding Wardrobe 180cm",
            merchant="Choice Furniture Superstore",
            url="https://click.linksynergy.com/deeplink?id=wardrobe1",
            price="599.00",
            currency="GBP",
        ),
        RakutenProduct(
            name="Modern 3 Door Wardrobe with Mirror",
            merchant="Choice Furniture Superstore",
            url="https://click.linksynergy.com/deeplink?id=wardrobe2",
            price="749.00",
            currency="GBP",
        ),
        RakutenProduct(
            name="Oak 4 Door Wardrobe",
            merchant="Choice Furniture Superstore",
            url="https://click.linksynergy.com/deeplink?id=wardrobe3",
            price="899.00",
            currency="GBP",
        ),
    ]

    matches = generator.relevant_products(feed, "wardrobe", "wardrobes")

    assert len(matches) == 3
    assert all("hanging rail" not in product.name.casefold() for product in matches)


def test_wardrobe_roundup_uses_furniture_checks_not_appliance_copy():
    topic = next(topic for topic in generator.RAKUTEN_TOPICS if topic[0] == "wardrobes")
    offers = [
        RakutenProduct(
            name=f"Modern {index + 2} Door Wardrobe",
            merchant="Choice Furniture Superstore",
            url=f"https://click.linksynergy.com/deeplink?id=wardrobe{index}",
            price=f"{499 + index * 100}.00",
            currency="GBP",
        )
        for index in range(3)
    ]

    article = generator.build_article(
        topic,
        offers,
        "uk",
        datetime(2026, 10, 5, tzinfo=timezone.utc),
    )

    content = article["content_html"].casefold()
    assert "hanging space" in content
    assert "power use" not in content
    assert "consumables" not in content


def test_air_purifier_gate_rejects_filters_and_refills():
    feed = [
        RakutenProduct(
            name="HEPA Filter for Basement Air Purifier",
            merchant="Sharper Image",
            url="https://click.linksynergy.com/deeplink?id=filter",
            price="39.99",
            currency="USD",
        ),
        RakutenProduct(
            name="High Performance Personal Air Purifier",
            merchant="Sharper Image",
            url="https://click.linksynergy.com/deeplink?id=purifier",
            price="159.99",
            currency="USD",
        ),
    ]

    matches = generator.relevant_products(feed, "air purifier", "air-purifiers")

    assert [product.name for product in matches] == ["High Performance Personal Air Purifier"]

