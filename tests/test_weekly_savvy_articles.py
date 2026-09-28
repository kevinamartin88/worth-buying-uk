from __future__ import annotations

from datetime import date

from generate_weekly_savvy_articles import build_article, selected_topic


def test_rotation_provides_52_unique_weekly_topics() -> None:
    combinations = {
        (selected_topic(week)[0]["slug"], selected_topic(week)[1][0])
        for week in range(1, 53)
    }
    assert len(combinations) == 52


def test_market_articles_are_distinct_and_publisher_ready() -> None:
    run_date = date(2026, 10, 3)
    uk = build_article("uk", run_date)
    us = build_article("us", run_date)

    assert uk["mode"] == us["mode"] == "publish"
    assert uk["slug"] != us["slug"]
    assert uk["source_sha"] != us["source_sha"]
    assert "www.worthbuyinguk.co.uk" in uk["content_html"]
    assert "www.worthbuyingusa.com" in us["content_html"]
    assert "ebay." not in uk["content_html"].casefold()
    assert "ebay." not in us["content_html"].casefold()
    assert len(uk["content_html"].split()) >= 650
    assert len(us["content_html"].split()) >= 650
    assert "{url}" in uk["x_text"]
    assert "{url}" in us["x_text"]
