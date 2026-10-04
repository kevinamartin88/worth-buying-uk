from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import generate_market_watch as market_watch


def test_market_watch_skips_without_enough_original_data(monkeypatch):
    monkeypatch.setattr(
        market_watch,
        "market_rows",
        lambda market: (
            [
                {
                    "title": "Product",
                    "current": 80.0,
                    "median": 100.0,
                    "change_pct": -20.0,
                    "currency": "GBP",
                    "checks": 3,
                    "guide_url": "",
                }
            ],
            1,
        ),
    )
    now = datetime(2026, 10, 1, tzinfo=ZoneInfo("Europe/London"))
    assert market_watch.render_market_watch("uk", now) is None


def test_market_watch_builds_original_data_story(monkeypatch):
    rows = []
    for index in range(8):
        rows.append(
            {
                "title": f"Product {index}",
                "current": 80.0 + index,
                "median": 100.0,
                "change_pct": -20.0 + index,
                "currency": "GBP",
                "checks": 4,
                "guide_url": f"https://example.com/{index}",
            }
        )
    monkeypatch.setattr(market_watch, "market_rows", lambda market: (rows, 8))
    now = datetime(2026, 10, 1, tzinfo=ZoneInfo("Europe/London"))
    article = market_watch.render_market_watch("uk", now)
    assert article is not None
    assert article["_seo"]["original_data"] is True
    assert article["_monetisation"]["primary_goal"] == "internal-link-to-money-guide"
    assert "retailer crossed-out RRPs" in article["content_html"]
    assert "https://example.com/0" in article["content_html"]
