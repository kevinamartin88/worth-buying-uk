from __future__ import annotations

import generate_daily_articles as daily


DASH_CAMS = next(topic for topic in daily.TOPICS if topic[0] == "dash-cams")
DEHUMIDIFIERS = next(topic for topic in daily.TOPICS if topic[0] == "dehumidifiers")


def test_google_shopping_is_primary_signal(monkeypatch, tmp_path):
    shopping = {
        "query": "dash cam",
        "source": "google-trends-google-shopping",
        "score": 72,
        "shopping_current": 64,
        "shopping_momentum": 1.4,
        "shopping_relative_to_anchor": 1.1,
    }
    monkeypatch.setattr(
        daily,
        "rank_topics_by_google_shopping",
        lambda topics, market: [(DASH_CAMS, shopping)],
    )
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, signal, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=2, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert signal == shopping
    assert gsc is None
    assert score == 72


def test_google_web_trend_is_secondary_when_shopping_unavailable(monkeypatch, tmp_path):
    trend = {
        "query": "dash cam",
        "traffic": 10000,
        "traffic_label": "10K+",
        "score": 45,
        "source": "google-trends-trending-now-rss",
    }
    monkeypatch.setattr(daily, "rank_topics_by_google_shopping", lambda topics, market: [])
    monkeypatch.setattr(
        daily,
        "rank_topics_by_trends",
        lambda topics, market: [(DASH_CAMS, trend)],
    )

    topic, signal, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=2, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert signal == trend
    assert gsc is None
    assert score == 45


def test_no_external_google_signal_still_publishes_seasonal_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "rank_topics_by_google_shopping", lambda topics, market: [])
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, signal, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=6, market="uk", month=9
    )

    assert topic == DEHUMIDIFIERS
    assert signal is None
    assert gsc is None
    assert score is None


def test_shopping_candidate_list_is_limited_and_commercial():
    available = list(daily.TOPICS)
    candidates = daily.shopping_candidate_topics(available, month=9, limit=10)

    assert len(candidates) == 10
    assert candidates[0][0] == "dehumidifiers"
    assert all(topic in available for topic in candidates)


def test_sunday_google_ranking_is_restricted_to_home_pool(monkeypatch, tmp_path):
    seen = {}

    def fake_shopping(topics, market):
        seen["keys"] = [topic[0] for topic in topics]
        return [(topics[0], {
            "query": topics[0][2],
            "source": "google-trends-google-shopping",
            "score": 70,
        })]

    monkeypatch.setattr(daily, "rank_topics_by_google_shopping", fake_shopping)
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, signal, _, _ = daily.pick_topic(
        tmp_path, year=2026, weekday=6, market="us", month=10
    )

    assert topic[0] in daily.SUNDAY_PRIORITY
    assert set(seen["keys"]).issubset(set(daily.SUNDAY_PRIORITY))
    assert "ssds" not in seen["keys"]
    assert "apple-watches" not in seen["keys"]
    assert topic[5] == "Home & Kitchen"


def test_sunday_fallback_remains_home_only(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "rank_topics_by_google_shopping", lambda topics, market: [])
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, signal, _, _ = daily.pick_topic(
        tmp_path, year=2026, weekday=6, market="uk", month=10
    )

    assert topic[0] in daily.SUNDAY_PRIORITY
    assert topic[5] == "Home & Kitchen"
    assert signal is None



def test_weekday_pool_stays_inside_authority_clusters(monkeypatch, tmp_path):
    seen = {}

    def fake_shopping(topics, market):
        seen["keys"] = [topic[0] for topic in topics]
        return [(topics[0], {
            "query": topics[0][2],
            "source": "google-trends-google-shopping",
            "score": 70,
        })]

    monkeypatch.setattr(daily, "rank_topics_by_google_shopping", fake_shopping)
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    daily.pick_topic(tmp_path, year=2026, weekday=2, market="uk", month=10)

    assert seen["keys"]
    assert set(seen["keys"]).issubset(set(daily.AUTHORITY_CORE_KEYS))


def test_listing_score_rejects_implausible_power_bank_claim():
    item = {
        "title": "9000000mAh Power Bank 4 USB Fast Charger HOT",
        "price": {"value": "24.99", "currency": "GBP"},
        "buyingOptions": ["FIXED_PRICE"],
        "seller": {"feedbackPercentage": "99.8", "feedbackScore": 5000},
        "image": {"imageUrl": "https://example.com/powerbank.jpg"},
    }
    assert daily.listing_score(item, 180, "GBP", query="USB C power bank") is None


def test_listing_score_rejects_unrelated_marketplace_accessory():
    item = {
        "title": "Universal replacement remote control",
        "price": {"value": "19.99", "currency": "GBP"},
        "buyingOptions": ["FIXED_PRICE"],
        "seller": {"feedbackPercentage": "99.8", "feedbackScore": 5000},
        "image": {"imageUrl": "https://example.com/remote.jpg"},
    }
    assert daily.listing_score(item, 1400, "GBP", query="4K smart TV") is None


def test_quick_picks_puts_affiliate_ctas_near_top(monkeypatch):
    item = {
        "title": "Example Air Fryer AF400",
        "price": {"value": "99.99", "currency": "GBP"},
        "condition": "New",
        "seller": {"feedbackPercentage": "99.9", "feedbackScore": 10000},
        "itemWebUrl": "https://www.ebay.co.uk/itm/123",
        "image": {"imageUrl": "https://example.com/fryer.jpg"},
    }
    html = daily.quick_picks_html([item], "uk", "air fryer")
    assert "Affiliate links" not in html
    assert "Check eBay UK price" in html
    assert "amazon.co.uk" not in html
    assert 'rel="sponsored nofollow"' in html



def test_evergreen_slug_reuses_existing_pillar(monkeypatch, tmp_path):
    article = {
        "slug": "best-air-fryers-worth-buying-uk-2026",
        "_generator": {"topic": "air-fryers"},
    }
    (tmp_path / "existing.json").write_text(
        __import__("json").dumps(article),
        encoding="utf-8",
    )
    monkeypatch.setattr(daily, "published_article_dir", lambda market: tmp_path)
    assert (
        daily.evergreen_article_slug("air-fryers", "uk")
        == "best-air-fryers-worth-buying-uk-2026"
    )


def test_new_pillar_gets_yearless_slug(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "published_article_dir", lambda market: tmp_path)
    assert daily.evergreen_article_slug("air-purifiers", "uk") == "best-air-purifiers-worth-buying-uk"



def test_quick_pick_card_uses_verified_marketplace_image():
    item = {
        "title": "Example Air Fryer AF400",
        "price": {"value": "99.99", "currency": "GBP"},
        "condition": "New",
        "seller": {"feedbackPercentage": "99.9", "feedbackScore": 10000},
        "itemWebUrl": "https://www.ebay.co.uk/itm/123",
        "image": {"imageUrl": "https://i.ebayimg.com/example.jpg"},
    }
    rendered = daily.quick_picks_html([item], "uk", "air fryer")
    assert "https://i.ebayimg.com/example.jpg" in rendered
    assert 'loading="lazy"' in rendered
    assert 'alt="Example Air Fryer AF400"' in rendered



def test_editorial_trust_box_is_transparent(monkeypatch):
    monkeypatch.setattr(
        daily,
        "_site_page_url",
        lambda market, key: "https://example.com/methodology",
    )
    rendered = daily.editorial_trust_html("uk", "4 October 2026")
    assert "How we choose our picks:" in rendered
    assert "data-led comparisons" in rendered
    assert "rather than market hype" in rendered
    assert "https://example.com/methodology" in rendered
    assert "Affiliate disclosure:" not in rendered
    assert "Prices checked:" in rendered
    assert "Retailer links may be affiliate links" in rendered
    assert "not on which retailer pays the highest commission" in rendered




def test_daily_feature_metadata_can_mark_refresh():
    article = {
        "_promotion": {
            "promotion_token": "2026-10-06:us:best-air-fryers",
            "is_refresh": False,
        }
    }
    article["_promotion"]["is_refresh"] = True
    assert article["_promotion"]["is_refresh"] is True
