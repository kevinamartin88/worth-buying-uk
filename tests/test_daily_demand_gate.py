from __future__ import annotations

import generate_daily_articles as daily


DASH_CAMS = next(topic for topic in daily.TOPICS if topic[0] == "dash-cams")
DEHUMIDIFIERS = next(topic for topic in daily.TOPICS if topic[0] == "dehumidifiers")


def test_no_google_demand_uses_seasonal_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(daily, "rank_topics_by_search_console", lambda topics, market: [])
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, trend, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=6, market="uk", month=9
    )

    assert topic == DEHUMIDIFIERS
    assert trend is None
    assert gsc is None
    assert score is None


def test_weak_live_trend_beats_blind_fallback(monkeypatch, tmp_path):
    weak = {
        "query": "dash cam",
        "traffic": 1000,
        "traffic_label": "1K+",
        "score": daily.MIN_TREND_DEMAND_SCORE - 0.01,
    }
    monkeypatch.setattr(daily, "rank_topics_by_search_console", lambda topics, market: [])
    monkeypatch.setattr(
        daily,
        "rank_topics_by_trends",
        lambda topics, market: [(DASH_CAMS, weak)],
    )

    topic, trend, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=6, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert trend == weak
    assert gsc is None
    assert score == weak["score"]


def test_current_trend_can_qualify_topic(monkeypatch, tmp_path):
    signal = {
        "query": "dash cam",
        "traffic": 10000,
        "traffic_label": "10K+",
        "score": daily.MIN_TREND_DEMAND_SCORE + 5,
    }
    monkeypatch.setattr(daily, "rank_topics_by_search_console", lambda topics, market: [])
    monkeypatch.setattr(
        daily,
        "rank_topics_by_trends",
        lambda topics, market: [(DASH_CAMS, signal)],
    )

    topic, trend, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=1, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert trend == signal
    assert gsc is None
    assert score == signal["score"]


def test_strong_gsc_query_can_qualify_topic(monkeypatch, tmp_path):
    signal = {
        "query": "best dash cams uk",
        "impressions": 120,
        "clicks": 3,
        "position": 12,
        "score": daily.MIN_GSC_DEMAND_SCORE + 5,
    }
    monkeypatch.setattr(
        daily,
        "rank_topics_by_search_console",
        lambda topics, market: [(DASH_CAMS, signal)],
    )
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, trend, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=2, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert trend is None
    assert gsc == signal
    assert score >= signal["score"]


def test_tiny_gsc_sample_is_best_available_before_seasonal_fallback(monkeypatch, tmp_path):
    signal = {
        "query": "best dash cams uk",
        "impressions": daily.MIN_GSC_IMPRESSIONS - 1,
        "clicks": 1,
        "position": 9,
        "score": 95,
    }
    monkeypatch.setattr(
        daily,
        "rank_topics_by_search_console",
        lambda topics, market: [(DASH_CAMS, signal)],
    )
    monkeypatch.setattr(daily, "rank_topics_by_trends", lambda topics, market: [])

    topic, trend, gsc, score = daily.pick_topic(
        tmp_path, year=2026, weekday=2, market="uk", month=9
    )

    assert topic == DASH_CAMS
    assert trend is None
    assert gsc == signal
    assert score == signal["score"]
