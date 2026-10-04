from __future__ import annotations

import json

from src import site_pages


def test_methodology_is_transparent_about_affiliate_model():
    page = site_pages.methodology_page("uk")
    text = page["content"].casefold()
    assert "affiliate-funded" in text
    assert "commission" in text
    assert "not laboratory tests" in text
    assert "do not claim hands-on testing" in text


def test_cluster_page_links_only_matching_guides():
    rows = [
        {
            "title": "Best Air Fryers",
            "url": "https://example.com/air",
            "cluster": "Kitchen & Small Appliances",
            "description": "Air fryer guide",
            "checked": "2026-10-04",
        }
    ]
    page = site_pages.cluster_page("Kitchen & Small Appliances", rows, "uk")
    assert "Best Air Fryers" in page["content"]
    assert "https://example.com/air" in page["content"]
    assert "affiliate commission" in page["content"]


def test_load_catalog_groups_existing_published_article(monkeypatch, tmp_path):
    articles = tmp_path / "articles"
    articles.mkdir()
    published = tmp_path / "published.json"
    pages = tmp_path / "pages.json"

    article = {
        "slug": "best-air-fryers",
        "title": "Best Air Fryers",
        "source_sha": "2026-10-04-air-fryers-uk-daily-v6",
        "_generator": {"topic": "air-fryers"},
        "_seo": {
            "authority_cluster": "Kitchen & Small Appliances",
            "description": "Compare air fryers",
            "last_checked_iso": "2026-10-04",
        },
        "_monetisation": {"primary_goal": "qualified-affiliate-click"},
    }
    (articles / "best-air-fryers.json").write_text(json.dumps(article), encoding="utf-8")
    published.write_text(
        json.dumps(
            {
                "best-air-fryers": {
                    "status": "published",
                    "url": "https://example.com/air",
                    "source_file": "best-air-fryers.json",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setitem(
        site_pages.MARKET,
        "uk",
        {
            "site": "Worth Buying UK",
            "region": "UK",
            "articles": articles,
            "published": published,
            "page_state": pages,
        },
    )

    catalog = site_pages.load_catalog("uk")
    assert len(catalog) == 1
    assert catalog[0]["cluster"] == "Kitchen & Small Appliances"
    assert catalog[0]["url"] == "https://example.com/air"
