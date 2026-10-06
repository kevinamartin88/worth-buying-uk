from __future__ import annotations

from src.us_targeting import prepare_us_article, us_url, localize_text, localize_html, validate_us_copy, us_audience_hours

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.youtube import YouTubeClient
from src.youtube_shorts import (
    MARKET_CONFIG,
    build_short_video,
    publication_fingerprint,
    short_description,
    short_title,
)


ROOT = Path(__file__).resolve().parent
CONFIG = {
    "uk": {
        "articles": ROOT / "articles",
        "blogger_state": ROOT / "state" / "articles_published.json",
        "youtube_state": ROOT / "state" / "youtube_uk_published.json",
        "hero_dir": ROOT / "assets" / "ai" / "uk",
        "channel_id": "UCqa0qql1Rrj8okQnTPgTT5Q",
    },
    "us": {
        "articles": ROOT / "articles-us",
        "blogger_state": ROOT / "state" / "articles_us_published.json",
        "youtube_state": ROOT / "state" / "youtube_us_published.json",
        "hero_dir": ROOT / "assets" / "ai" / "us",
        "channel_id": "UCJb8X5WBYyfc71IX5fn1zrw",
    },
}


def load_json(path: Path, default):
    if not path.exists():
        return default.copy() if hasattr(default, "copy") else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default.copy() if hasattr(default, "copy") else default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def eligible_articles(market: str, only_slug: str | None = None):
    config = CONFIG[market]
    blogger_state = load_json(config["blogger_state"], {})
    for article_path in sorted(config["articles"].glob("*.json")):
        article = load_json(article_path, {})
        slug = str(article.get("slug", ""))
        if not slug or (only_slug and slug != only_slug):
            continue
        post = blogger_state.get(slug, {})
        blog_url = str(post.get("url") or "").strip()
        if article.get("mode", "publish").strip().lower() != "publish":
            continue
        if post.get("status") != "published" or not blog_url:
            continue
        if market == "us":
            article = prepare_us_article(article)
            blog_url = us_url(blog_url)
        yield article, blog_url


def baseline_existing(market: str, state: dict) -> None:
    for article, blog_url in eligible_articles(market):
        slug = article["slug"]
        state.setdefault(
            slug,
            {
                "status": "baseline",
                "blog_url": blog_url,
                "publication_fingerprint": publication_fingerprint(article, blog_url),
            },
        )
    state["_meta"] = {
        "initialized": True,
        "version": 1,
        "note": "Existing articles were baselined so only future publications or updates create Shorts.",
    }
    save_json(CONFIG[market]["youtube_state"], state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and upload Blogger companion Shorts")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument("--article", help="Generate/upload only this article slug")
    parser.add_argument("--dry-run", action="store_true", help="Render but do not upload")
    parser.add_argument("--backfill", action="store_true", help="Allow existing articles to upload")
    args = parser.parse_args()

    market = args.market
    if market == "us" and not args.dry_run and not us_audience_hours():
        print("[deferred] USA Shorts resume during 09:00–21:00 Eastern.")
        return
    config = CONFIG[market]
    state = load_json(config["youtube_state"], {})

    if not args.dry_run and not YouTubeClient.configured(market):
        print(f"[youtube-skip] {market.upper()} YouTube OAuth secrets are not configured.")
        return

    if (
        not args.dry_run
        and not args.backfill
        and not args.article
        and not state.get("_meta", {}).get("initialized")
    ):
        baseline_existing(market, state)
        print(
            f"[youtube-baseline] Recorded existing {market.upper()} articles. "
            "Future publications and updates will create Shorts."
        )
        return

    client = None if args.dry_run else YouTubeClient.from_env(market)
    if client:
        channel = client.verify_channel(config["channel_id"])
        print(f"[youtube-channel] {channel['snippet']['title']} ({channel['id']})")

    candidates = list(eligible_articles(market, args.article))
    if args.article and not candidates:
        raise RuntimeError(
            f"Article {args.article!r} has no confirmed published Blogger URL for {market.upper()}."
        )

    uploaded = 0
    for article, blog_url in candidates:
        slug = article["slug"]
        fingerprint = publication_fingerprint(article, blog_url)
        if not args.dry_run and state.get(slug, {}).get("publication_fingerprint") == fingerprint:
            print(f"[youtube-skip] {slug}: unchanged")
            continue

        title = short_title(article)
        if client:
            existing = client.find_uploaded_video(title=title, blog_url=blog_url)
            if existing:
                video_id = existing["id"]
                state[slug] = {
                    "status": "published",
                    "video_id": video_id,
                    "video_url": f"https://www.youtube.com/shorts/{video_id}",
                    "blog_url": blog_url,
                    "publication_fingerprint": fingerprint,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                    "reconciled_from_channel": True,
                }
                state.setdefault("_meta", {"initialized": True, "version": 1})
                save_json(config["youtube_state"], state)
                print(
                    f"[youtube-existing] {slug}: "
                    f"https://www.youtube.com/shorts/{video_id}"
                )
                continue

        hero_path = config["hero_dir"] / f"{slug}.jpg"
        if not hero_path.exists():
            print(f"[youtube-skip] {slug}: no generated hero image")
            continue
        logo_path = ROOT / "assets" / "brand" / MARKET_CONFIG[market]["logo"]
        with tempfile.TemporaryDirectory(prefix=f"worth-buying-{market}-short-") as temp:
            temp_path = Path(temp)
            video_path = temp_path / f"{slug}.mp4"
            build_short_video(
                article,
                market=market,
                hero_path=hero_path,
                logo_path=logo_path,
                output_path=video_path,
                work_dir=temp_path / "slides",
            )
            if args.dry_run:
                output = ROOT / "outputs" / "youtube-shorts" / market / video_path.name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(video_path.read_bytes())
                print(f"[youtube-dry-run] Rendered {output}")
                continue

            privacy = os.getenv("YOUTUBE_PRIVACY_STATUS", "public").strip().lower()
            tags = list(
                dict.fromkeys(
                    [
                        *[str(label) for label in article.get("labels", [])],
                        "Buying Guide",
                        MARKET_CONFIG[market]["brand"],
                        "Shorts",
                    ]
                )
            )[:30]
            response = client.upload_video(
                video_path,
                title=title,
                description=short_description(article, blog_url, market),
                tags=tags,
                privacy_status=privacy,
            )

        video_id = response["id"]
        state[slug] = {
            "status": "published",
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/shorts/{video_id}",
            "blog_url": blog_url,
            "publication_fingerprint": fingerprint,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("_meta", {"initialized": True, "version": 1})
        save_json(config["youtube_state"], state)
        uploaded += 1
        print(f"[youtube-published] {slug}: https://www.youtube.com/shorts/{video_id}")

    print(f"[youtube-complete] Uploaded {uploaded} {market.upper()} Short(s).")


if __name__ == "__main__":
    main()
