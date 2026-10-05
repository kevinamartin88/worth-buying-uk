"""Regenerate five existing USA guides with verified current products."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import generate_daily_articles as daily
from src.usa_conversion import PILOT_TOPICS, EXPERIMENT


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
        # Preserve manual publication identity/metadata while reusing the slug.
        for field in ("_manual_publish",):
            if field in previous:
                article[field] = previous[field]
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
