from __future__ import annotations

from datetime import date, timedelta
from src.article_copy import clean_article_disclosures

from generate_weekly_savvy_articles import (
    build_article,
    selected_topic_for_date,
)


def test_rotation_provides_52_distinct_monday_and_saturday_topics() -> None:
    first_monday = date(2026, 1, 5)
    scheduled_dates = []
    for week_offset in range(26):
        monday = first_monday + timedelta(weeks=week_offset)
        scheduled_dates.extend((monday, monday + timedelta(days=5)))
    combinations = {
        (
            selected_topic_for_date(run_date)[0]["slug"],
            selected_topic_for_date(run_date)[1][0],
        )
        for run_date in scheduled_dates
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


def test_monday_and_saturday_create_distinct_advice_articles() -> None:
    monday = date(2026, 10, 5)
    saturday = date(2026, 10, 10)

    monday_article = build_article("uk", monday)
    saturday_article = build_article("uk", saturday)

    assert selected_topic_for_date(monday) != selected_topic_for_date(saturday)
    assert monday_article["slug"] != saturday_article["slug"]
    assert monday_article["source_sha"] != saturday_article["source_sha"]
    assert monday_article["title"].startswith("Savvy Buyer Monday:")
    assert saturday_article["title"].startswith("Savvy Buyer Saturday:")


def test_other_weekdays_including_sunday_are_rejected() -> None:
    for unsupported_date in (date(2026, 10, 6), date(2026, 10, 11)):
        try:
            build_article("uk", unsupported_date)
        except ValueError as exc:
            assert "Monday and Saturday" in str(exc)
        else:
            raise AssertionError(f"{unsupported_date:%A} generation should be rejected")


def test_published_savvy_guides_keep_advice_first_and_one_footer_disclosure():
    for market in ("uk", "us"):
        for run_date in (date(2026, 10, 5), date(2026, 10, 10)):
            article = build_article(market, run_date)
            published = clean_article_disclosures(article["content_html"])
            assert published.index("Before you buy") < published.index("This week's buying lesson")
            assert published.index("Your five-minute checkout checklist") < published.index("About this guide")
            assert published.index("About this guide") < published.index("Affiliate disclosure:")
            assert published.count("Affiliate disclosure:") == 1
            assert clean_article_disclosures(published) == published


