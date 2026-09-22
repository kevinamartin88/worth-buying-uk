from __future__ import annotations

import json
import os
from pathlib import Path

from src.bluesky import BlueskyClient


ROOT = Path(__file__).resolve().parent
BLOG_STATE = ROOT / "state" / "articles_published.json"
STATE = ROOT / "state" / "bluesky_published.json"
AI_IMAGE_DIR = ROOT / "assets" / "ai" / "uk"
FALLBACK_IMAGE_DIR = ROOT / "assets" / "x" / "uk"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def initialize_baseline(blog_state: dict) -> None:
    baseline = {}
    for slug, item in sorted(blog_state.items()):
        if item.get("status") != "published":
            continue
        baseline[slug] = {
            "baseline": True,
            "title": item.get("title"),
            "url": item.get("url"),
            "source_sha": item.get("source_sha"),
        }
    save_json(STATE, baseline)
    print(
        f"Initialized UK Bluesky publication baseline with {len(baseline)} existing article(s); "
        "no historical Bluesky posts sent."
    )


def main() -> None:
    handle = os.getenv("BLUESKY_UK_HANDLE", "").strip()
    app_password = os.getenv("BLUESKY_UK_APP_PASSWORD", "").strip()
    if not handle or not app_password:
        print("[skip] BLUESKY_UK_HANDLE or BLUESKY_UK_APP_PASSWORD is not configured")
        return

    blog_state = load_json(BLOG_STATE)
    if not STATE.exists():
        initialize_baseline(blog_state)
        return

    state = load_json(STATE)
    bluesky = BlueskyClient(handle=handle, app_password=app_password, language="en-GB")

    posted = 0
    for slug, item in sorted(blog_state.items()):
        if item.get("status") != "published" or slug in state:
            continue

        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue

        ai_image_path = AI_IMAGE_DIR / f"{slug}.jpg"
        fallback_image_path = FALLBACK_IMAGE_DIR / f"{slug}.png"
        if ai_image_path.exists():
            image_path = ai_image_path
        elif fallback_image_path.exists():
            image_path = fallback_image_path
        else:
            image_path = None

        result = bluesky.publish(
            title=title,
            url=url,
            market_name="UK",
            image_path=image_path,
        )
        state[slug] = {
            "status": "published",
            "bluesky_uri": result["uri"],
            "bluesky_cid": result["cid"],
            "bluesky_url": result["web_url"],
            "title": title,
            "url": url,
            "source_sha": item.get("source_sha"),
            "image_path": str(image_path.relative_to(ROOT)) if image_path else None,
        }
        save_json(STATE, state)
        posted += 1
        print(f"[bluesky-posted] {title}: {result['web_url']}")

    save_json(STATE, state)
    print(f"UK Bluesky publishing complete: {posted} new post(s).")


if __name__ == "__main__":
    main()
