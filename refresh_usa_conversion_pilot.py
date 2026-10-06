"""Regenerate five existing USA guides with verified current products."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

import generate_daily_articles as daily
from src.usa_conversion import PILOT_TOPICS, EXPERIMENT


PRESENTATION_FIELDS = (
    "title",
    "labels",
    "hero_image_kicker",
    "pinterest_title",
    "pinterest_subtitle",
    "x_image_title",
    "x_kicker",
    "x_subtitle",
    "x_text",
)


def preserve_presentation_metadata(article: dict, previous: dict) -> dict:
    """Do not let conversion-card refreshes erase daily/event presentation state."""
    for field in ("_manual_publish", "_promotion", "_event", "hero_visual_revision"):
        if field in previous:
            article[field] = deepcopy(previous[field])

    # Active event presentation (for example Prime Big Deal Days) must survive
    # a product-card refresh. The event cleanup script owns restoring these
    # fields after the event ends.
    if previous.get("_event"):
        for field in PRESENTATION_FIELDS:
            if field in previous:
                article[field] = deepcopy(previous[field])

    return article


def main():
    now = datetime.now(timezone.utc)
    report = {"experiment": EXPERIMENT, "generated_at": now.isoformat(), "articles": []}
    pending = []
    topics = {topic[0]: topic for topic in daily.TOPICS}
    # Prepare all five before writing any article, including legacy manual guides
    # whose permanent slugs are resolved from their existing filenames.
    for key in PILOT_TOPICS:
        article = daily.build_article(topics[key], "us", now.year)
        if not article["_generator"]["live_ebay_picks"]:
            raise RuntimeError(f"Pilot blocked: {key} has fewer than three verified current products")
        path = daily.ROOT / "articles-us" / f'{article["slug"]}.json'
        if not path.exists():
            raise RuntimeError(f"Pilot requires an existing guide: {key}")
        previous = daily.load_json(path)
        article = preserve_presentation_metadata(article, previous)
        article["_conversion_pilot"] = {"experiment": EXPERIMENT, "prepared_at": now.isoformat()}
        pending.append((path, article))
        report["articles"].append({"slug": article["slug"], "topic": key,
                                   "verified_products": article["_generator"]["pick_count"]})
    for path, article in pending:
        daily.save_json(path, article)
    daily.save_json(daily.ROOT / "state" / "usa_conversion_pilot.json", report)
    print(f"[usa-conversion] Prepared {len(pending)} existing guides for automatic publication")


if __name__ == "__main__":
    main()
