from __future__ import annotations

import json

import cleanup_blogger_duplicates as cleanup


def test_duplicate_groups_keeps_clean_url_and_matches_only_same_title():
    posts = [
        {
            "id": "clean",
            "title": "Best Refurbished Tablets to Buy in the UK (2026)",
            "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk.html",
        },
        {
            "id": "dup1",
            "title": "Best Refurbished Tablets to Buy in the UK (2026)",
            "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk_01543200660.html",
        },
        {
            "id": "other",
            "title": "Different article",
            "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk_99999999999.html",
        },
    ]

    groups = cleanup.duplicate_groups(posts)
    assert len(groups) == 1
    primary, duplicates = groups[0]
    assert primary["id"] == "clean"
    assert [post["id"] for post in duplicates] == ["dup1"]


def test_update_state_repoints_suffix_url_to_clean_primary(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "best-refurbished-tablets-uk-2026": {
                    "post_id": "dup1",
                    "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk_01543200660.html",
                    "title": "Best Refurbished Tablets to Buy in the UK (2026)",
                    "status": "published",
                    "source_sha": "keep-me",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(cleanup.STATE_PATHS, "uk", state_path)

    primary = {
        "id": "clean",
        "title": "Best Refurbished Tablets to Buy in the UK (2026)",
        "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk.html",
    }
    duplicate = {
        "id": "dup1",
        "title": primary["title"],
        "url": "https://www.worthbuyinguk.co.uk/2026/09/best-refurbished-tablets-to-buy-in-uk_01543200660.html",
    }

    changed = cleanup.update_state("uk", [(primary, [duplicate])])
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    entry = saved["best-refurbished-tablets-uk-2026"]

    assert changed == 1
    assert entry["post_id"] == "clean"
    assert entry["url"].endswith("best-refurbished-tablets-to-buy-in-uk.html")
    assert entry["source_sha"] == "keep-me"


def test_no_cleanup_without_exact_clean_primary():
    posts = [
        {
            "id": "dup1",
            "title": "Example",
            "url": "https://www.example.com/2026/09/example_123456789.html",
        }
    ]
    assert cleanup.duplicate_groups(posts) == []
