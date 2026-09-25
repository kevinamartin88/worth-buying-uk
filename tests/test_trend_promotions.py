from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from generate_daily_articles import TOPICS, pick_topic
from promote_trending_guides import choose_promotion, post_text
from src.google_trends import score_topic_against_trend


NOW = datetime(2026, 9, 25, 20, tzinfo=timezone.utc)
ARTICLES = {
    "best-air-fryers": {
        "status": "published",
        "title": "Best Air Fryers Worth Buying in the UK (2026)",
        "url": "https://example.com/air-fryers",
    },
    "draft-air-fryers": {
        "status": "draft",
        "title": "Best Air Fryers for Families",
        "url": "https://example.com/draft",
    },
}


def test_large_family_air_fryer_trend_selects_published_guide():
    trend = {"query": "large family airfryers", "traffic": 100_000}
    chosen = choose_promotion(ARTICLES, [trend], {}, NOW)
    assert chosen is not None
    assert chosen["slug"] == "best-air-fryers"
    assert "large family" not in post_text(chosen["article"]).casefold()


def test_no_match_for_news_or_unrelated_query():
    for query in ("air fryer fire", "football results"):
        assert choose_promotion(ARTICLES, [{"query": query, "traffic": 100_000}], {}, NOW) is None


def test_daily_and_article_cooldowns():
    trend = [{"query": "large family air fryers", "traffic": 100_000}]
    assert choose_promotion(ARTICLES, trend, {"last_posted_date": NOW.date().isoformat()}, NOW) is None
    history = {"articles": {"best-air-fryers": (NOW - timedelta(days=2)).isoformat()}}
    assert choose_promotion(ARTICLES, trend, history, NOW) is None


def test_plural_air_fryer_match():
    topic = ("air-fryers", "Air Fryers", "air fryer")
    assert score_topic_against_trend(topic, {"query": "large family airfryers", "traffic": 100_000}) >= 45


def test_fresh_trend_controls_new_guide_when_search_console_ranks_other_topic():
    family = next(topic for topic in TOPICS if topic[0] == "large-capacity-air-fryers")
    television = next(topic for topic in TOPICS if topic[0] == "tvs")
    with patch("generate_daily_articles.topic_already_covered", return_value=False), patch(
        "generate_daily_articles.rank_topics_by_search_console", return_value=[(television, {"score": 99})]
    ), patch(
        "generate_daily_articles.rank_topics_by_trends",
        return_value=[(family, {"query": "large family airfryers", "score": 75, "traffic": 100_000})],
    ):
        chosen, trend, _, _ = pick_topic(Path("."), 2026, 4, "uk")
    assert chosen == family
    assert trend["query"] == "large family airfryers"
