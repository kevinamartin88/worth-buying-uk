from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import generate_daily_articles as daily

ROOT = Path(__file__).resolve().parents[1]


def refresh_topic(market: str, topic_key: str) -> Path:
    if market not in {"uk", "us"}:
        raise ValueError("market must be 'uk' or 'us'")

    topic = next((row for row in daily.TOPICS if row[0] == topic_key), None)
    if topic is None:
        raise ValueError(f"Unknown daily topic: {topic_key}")

    now = datetime.now(daily.LONDON_TZ)
    article = daily.build_article(topic, market, now.year)

    promotion = article.setdefault("_promotion", {})
    promotion["daily_featured_date"] = now.date().isoformat()
    promotion["promotion_token"] = (
        f"{now.date().isoformat()}:{market}:{article['slug']}:manual-topic-refresh-v1"
    )
    promotion["return_to_top"] = True
    promotion["is_refresh"] = True

    article["source_sha"] = (
        f"{now.date().isoformat()}-{topic_key}-{market}-daily-v7-variety-refresh"
    )

    directory = ROOT / ("articles" if market == "uk" else "articles-us")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{article['slug']}.json"
    target.write_text(
        json.dumps(article, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[topic-refresh] {market.upper()} {topic_key} -> {target.relative_to(ROOT)}")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()
    refresh_topic(args.market, args.topic)
