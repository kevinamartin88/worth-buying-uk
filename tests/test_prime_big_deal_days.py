from __future__ import annotations

from datetime import date

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
    row = prime.generate_one_market(
        state,
        market="uk",
        run_date=date(2026, 10, 6),
        year=2026,
    )
    assert row is not None
    assert row["slot"] == 1
    assert len(state["days"]["2026-10-06"]["uk"]["published"]) == 1
