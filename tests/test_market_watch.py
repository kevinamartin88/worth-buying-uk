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


def test_old_bad_recommendations_do_not_return_as_price_movers(monkeypatch):
    history={'daily|uk|bad':{'title':'USB Power Cable Adapter for Fire TV Stick','article_slug':'best-streaming-devices-worth-buying-uk'},
             'daily|uk|good':{'title':'Roku Streaming Stick 4K with Remote','article_slug':'best-streaming-devices-worth-buying-uk'}}
    monkeypatch.setattr(market_watch,'load_json',lambda path: history if path==market_watch.HISTORY else {})
    monkeypatch.setattr(market_watch,'valid_observations',lambda *args:[{'price':x,'currency':'GBP'} for x in [100,90,80]])
    monkeypatch.setattr(market_watch,'chart_html',lambda *args:'')
    rows,count=market_watch.market_rows('uk')
    assert count==1 and len(rows)==1 and rows[0]['title'].startswith('Roku')
