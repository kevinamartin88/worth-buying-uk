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
