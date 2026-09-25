"""Share at most one relevant, already-published guide per market and day."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.buffer import BufferClient
from src.google_trends import BLOCKED_TITLE_TOKENS, fetch_trending_searches, score_topic_against_trend, tokens


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "trend_promotions.json"
ARTICLE_STATE = {
    "uk": ROOT / "state" / "articles_published.json",
    "us": ROOT / "state" / "articles_us_published.json",
}
CHANNEL_NAMES = {"uk": "Worth Buying UK", "us": "Worth Buying USA"}
BLOCKED_QUERIES = BLOCKED_TITLE_TOKENS | {
    "fire", "explosion", "broken", "scam", "court", "arrest", "accident", "fault", "faulty",
}


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def choose_promotion(articles: dict, trends: list[dict], history: dict, now: datetime) -> dict | None:
    market_history = history.get("articles", {})
    if history.get("last_posted_date") == now.date().isoformat():
        return None

    candidates = []
    for slug, article in articles.items():
        if article.get("status") != "published" or not article.get("url") or not article.get("title"):
            continue
        last_posted = market_history.get(slug)
        if last_posted:
            try:
                if now - datetime.fromisoformat(last_posted) < timedelta(days=14):
                    continue
            except ValueError:
                pass
        title = str(article["title"])
        article_tokens = tokens(title)
        for trend in trends:
            query = str(trend.get("query") or "")
            query_tokens = tokens(query)
            if len(article_tokens & query_tokens) < 2:
                continue
            if set(query.casefold().split()) & BLOCKED_QUERIES:
                continue
            topic = (slug, title, title)
            score = score_topic_against_trend(topic, trend)
            if score < 45:
                continue
            candidates.append((score, int(trend.get("traffic") or 0), slug, article, trend))

    if not candidates:
        return None
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    score, _, slug, article, trend = candidates[0]
    return {"slug": slug, "article": article, "trend": trend, "score": score}


def post_text(article: dict) -> str:
    title = " ".join(str(article["title"]).split())
    url = str(article["url"])
    suffix = f"\n\nAffiliate link: {url}"
    prefix = "Comparing options today? Our buying guide covers what to check before you buy:\n\n"
    limit = 280 - len(prefix) - len(suffix)
    if len(title) > limit:
        title = title[: limit - 1].rstrip() + "…"
    return prefix + title + suffix


def run_market(market: str, dry_run: bool, now: datetime) -> None:
    history = load_json(STATE_PATH)
    market_history = history.get(market, {})
    articles = load_json(ARTICLE_STATE[market])
    trends = fetch_trending_searches(market)
    choice = choose_promotion(articles, trends, market_history, now)
    if not choice:
        print(f"[skip] {market.upper()}: no fresh, strong, eligible guide match")
        return

    article = choice["article"]
    print(f"[match] {market.upper()}: {choice['slug']} matched {choice['trend']['query']!r} (score={choice['score']})")
    if dry_run:
        print("[dry-run] Buffer was not called")
        return

    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    if not api_key:
        print("[skip] BUFFER_API_KEY is not configured")
        return
    buffer = BufferClient(api_key, CHANNEL_NAMES[market])
    created = buffer.create_post(text=post_text(article), mode="shareNow")
    market_history.setdefault("articles", {})[choice["slug"]] = now.isoformat()
    market_history["last_posted_date"] = now.date().isoformat()
    market_history["last_post_id"] = str(created["id"])
    market_history["last_query"] = choice["trend"]["query"]
    history[market] = market_history
    save_json(STATE_PATH, history)
    print(f"[accepted] {market.upper()}: Buffer post {created['id']}; promotion recorded")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    for market in ("uk", "us"):
        run_market(market, args.dry_run, now)


if __name__ == "__main__":
    main()
