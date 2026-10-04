from __future__ import annotations

import generate_supporting_articles as support


def test_weekly_base_topic_is_always_core_authority_topic():
    for market in ("uk", "us"):
        for week in (1, 2, 10, 25, 52):
            topic = support.base_topic_for_week(week, market)
            assert topic[0] in support.daily.AUTHORITY_CORE_KEYS


def test_budget_angle_creates_commercial_long_tail():
    base = next(topic for topic in support.daily.TOPICS if topic[0] == "air-fryers")
    topic = support.support_topic(base, "uk", iso_week=1)
    assert topic[0].startswith("air-fryers-under-")
    assert "Under £" in topic[1]
    assert topic[3] < base[3]


def test_refurbished_angle_targets_refurbished_query():
    base = next(topic for topic in support.daily.TOPICS if topic[0] == "tvs")
    topic = support.support_topic(base, "us", iso_week=2)
    assert topic[0].startswith("refurbished-")
    assert topic[2].startswith("refurbished ")


def test_support_article_retains_parent_cluster(monkeypatch):
    base = next(topic for topic in support.daily.TOPICS if topic[0] == "dash-cams")

    def fake_build(topic, market, year):
        return {
            "slug": "support-dash-cams",
            "title": "Support Dash Cams",
            "content_html": "<p>Body</p>",
            "_seo": {},
            "_monetisation": {},
            "_generator": {},
        }

    monkeypatch.setattr(support.daily, "build_article", fake_build)
    monkeypatch.setattr(support, "_pillar_url", lambda *args: "https://example.com/pillar")

    article = support.build_support_article(base, "uk", 2026, 3)
    assert article["_seo"]["authority_cluster"] == "Motoring"
    assert article["_generator"]["parent_topic"] == "dash-cams"
    assert "https://example.com/pillar" in article["content_html"]
