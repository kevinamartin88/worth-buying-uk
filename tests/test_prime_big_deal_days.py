from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import generate_prime_big_deal_articles as prime


def test_prime_mode_is_hard_limited_to_event_dates():
    assert prime.event_active(date(2026, 10, 6))
    assert prime.event_active(date(2026, 10, 7))
    assert not prime.event_active(date(2026, 10, 5))
    assert not prime.event_active(date(2026, 10, 8))


def test_prime_decoration_is_commercial_but_does_not_invent_discount():
    base = {
        "slug": "best-robot-vacuums-worth-buying-uk-2026",
        "title": "Best Robot Vacuum Cleaners Worth Buying in the UK (2026)",
        "labels": ["Home & Kitchen", "Buying Guides", "UK"],
        "hero_image_kicker": "ROBOT VACUUM GUIDE",
        "pinterest_title": "Robot Vacuums",
        "pinterest_subtitle": "Current options",
        "x_image_title": "Robot Vacuums",
        "x_kicker": "ROBOT VACUUM GUIDE",
        "x_subtitle": "Current options",
        "x_text": "Read the guide {url}",
        "content_html": "<p>Buyer-first intro.</p><h2>Options</h2>",
        "_seo": {"primary_keyword": "robot vacuums uk"},
        "_monetisation": {},
        "_generator": {"pick_count": 4, "live_ebay_picks": True},
        "_promotion": {},
        "source_sha": "old",
    }
    topic = prime.topic_by_key("robot-vacuums")
    article = prime.decorate_prime_article(
        base,
        topic=topic,
        market="uk",
        run_date=date(2026, 10, 6),
        refreshing=True,
    )
    assert article["title"].startswith("Prime Big Deal Days:")
    assert article["hero_image_kicker"] == "PRIME BIG DEAL DAYS"
    assert article["_promotion"]["is_refresh"] is True
    assert (
        article["_promotion"]["promotion_token"]
        == "2026-10-06:prime-big-deal-days:uk:best-robot-vacuums-worth-buying-uk-2026"
    )
    assert "6–7 October" in article["content_html"]
    assert "does not mean every item is a Prime-exclusive discount" in article["content_html"]
    assert "50% off" not in article["content_html"]
    assert article["_event"]["restore"]["title"] == base["title"]


def test_prime_banner_follows_buyer_first_intro():
    content = '<div><p>Useful opening for shoppers.</p><h2>Picks</h2></div>'
    rendered = prime._insert_event_banner(
        content,
        prime._event_banner(date(2026, 10, 6), "us"),
    )
    assert rendered.index("Useful opening for shoppers") < rendered.index(
        "Prime Big Deal Days price check"
    )


def test_each_run_caps_at_one_article_per_market(monkeypatch, tmp_path):
    state = {}
    base = {
        "slug": "best-large-capacity-air-fryers-worth-buying-uk",
        "title": "Best Large Capacity Air Fryers Worth Buying in the UK (2026)",
        "labels": ["Home & Kitchen", "UK"],
        "content_html": "<p>Buyer first.</p><h2>Picks</h2>",
        "_seo": {},
        "_monetisation": {},
        "_generator": {"live_ebay_picks": True, "pick_count": 4},
    }
    monkeypatch.setattr(prime, "ROOT", tmp_path)
    monkeypatch.setattr(prime.daily, "build_article", lambda *args, **kwargs: dict(base))
    monkeypatch.setattr(
        prime,
        "_amazon_prime_offers",
        lambda *args, **kwargs: [
            SimpleNamespace(
                title=f"Robot Vacuum {i}",
                price=199.99 + i,
                url=f"https://www.amazon.co.uk/dp/B00000000{i}",
                image_url=f"https://m.media-amazon.com/images/I/product{i}._SL1200_.jpg",
            )
            for i in range(1, 5)
        ],
    )
    row = prime.generate_one_market(
        state,
        market="uk",
        run_date=date(2026, 10, 6),
        year=2026,
    )
    assert row is not None
    assert row["slot"] == 1
    assert len(state["days"]["2026-10-06"]["uk"]["published"]) == 1


def test_prime_validation_requires_amazon_product_images():
    article = {
        "slug": "example",
        "content_html": (
            '<a href="https://www.amazon.co.uk/dp/B000000001">Amazon</a>'
            '<a href="https://www.amazon.co.uk/tryprimefree?tag=worthbuyin008-21">'
            'Check Amazon UK Prime eligibility</a>'
            '<img src="https://m.media-amazon.com/images/I/one.jpg">'
            '<img src="https://m.media-amazon.com/images/I/two.jpg">'
            '<img src="https://m.media-amazon.com/images/I/three.jpg">'
        ),
        "_monetisation": {"networks": ["Amazon"]},
    }
    prime.validate_prime_article(article, "uk")


def test_missing_amazon_credentials_publish_safe_search_fallback(monkeypatch, tmp_path):
    state = {}
    base = {
        "slug": "best-tvs-worth-buying-uk-2026",
        "title": "Best TVs Worth Buying in the UK (2026)",
        "labels": ["Tech", "UK"],
        "content_html": "<p>Buyer first.</p>",
        "_seo": {},
        "_monetisation": {},
        "_generator": {},
    }
    monkeypatch.setattr(prime, "ROOT", tmp_path)
    monkeypatch.setattr(prime.daily, "build_article", lambda *args, **kwargs: dict(base))

    def missing_credentials(*args, **kwargs):
        raise RuntimeError(
            "Amazon Creators API credentials are required for Prime product cards (uk)"
        )

    monkeypatch.setattr(prime, "_amazon_prime_offers", missing_credentials)

    row = prime.generate_one_market(
        state,
        market="uk",
        run_date=date(2026, 10, 7),
        year=2026,
    )

    assert row is not None
    assert row["slot"] == 1
    assert row["topic"] == "tvs"
    market = state["days"]["2026-10-07"]["uk"]
    assert len(market["published"]) == 1
    assert market["attempted"] == [{"topic": "tvs", "status": "published"}]

    article_path = tmp_path / "articles" / "best-tvs-worth-buying-uk-2026.json"
    article = prime.load_json(article_path)
    assert article["_generator"]["prime_amazon_search_fallback"] is True
    assert article["_monetisation"]["retailer_mode"] == "amazon-search-fallback"
    assert article["content_html"].count("amazon.co.uk/s?k=") >= 3
    assert "tag=worthbuyin008-21" in article["content_html"]
    assert "Amazon price checked:" not in article["content_html"]


def test_retryable_error_classifier_is_narrow():
    assert prime._retryable_build_error(
        RuntimeError("Amazon Creators API credentials are required for Prime product cards (uk)")
    )
    assert not prime._retryable_build_error(
        RuntimeError("Amazon returned only 1 usable TV offers with product images")
    )
