from __future__ import annotations

import json
import os
from pathlib import Path

from src.buffer import BufferClient


ROOT = Path(__file__).resolve().parent
BLOG_STATE = ROOT / "state" / "articles_us_published.json"
STATE = ROOT / "state" / "bluesky_us_published.json"
AI_IMAGE_DIR = ROOT / "assets" / "ai" / "us"
AI_IMAGE_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/ai/us"
FALLBACK_IMAGE_DIR = ROOT / "assets" / "x" / "us"
FALLBACK_IMAGE_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/x/us"


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
            "buffer_post_id": None,
            "title": item.get("title"),
            "url": item.get("url"),
            "source_sha": item.get("source_sha"),
            "baseline": True,
        }
    save_json(STATE, baseline)
    print(
        f"Initialized USA Bluesky publication baseline with {len(baseline)} existing article(s); "
        "no Bluesky posts sent."
    )


def build_text(title: str, url: str) -> str:
    suffix = f"\n\nAffiliate 🔗 {url}\n#WorthBuying #BuyingGuide"
    intro = f"🔎 {title}\n\nOur latest USA buying guide compares current options, value and practical buying checks."
    available = max(40, 300 - len(suffix))
    if len(intro) > available:
        intro = intro[: available - 1].rstrip() + "…"
    return intro + suffix


def main() -> None:
    if not os.getenv("BUFFER_API_KEY"):
        print("[skip] BUFFER_API_KEY is not configured")
        return

    blog_state = load_json(BLOG_STATE)
    if not STATE.exists():
        initialize_baseline(blog_state)
        return

    state = load_json(STATE)
    buffer = BufferClient.from_env()

    try:
        channel_id = buffer.find_bluesky_channel_id()
    except RuntimeError as exc:
        print(f"[skip] {exc}")
        return

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
            image_url = f"{AI_IMAGE_BASE}/{slug}.jpg"
        elif fallback_image_path.exists():
            image_url = f"{FALLBACK_IMAGE_BASE}/{slug}.png"
        else:
            image_url = None

        created = buffer.create_post(
            text=build_text(title, url),
            mode="shareNow",
            image_url=image_url,
            channel_id=channel_id,
        )
        post_id = str(created["id"])
        final = buffer.wait_for_post(post_id, timeout_seconds=90)
        status = str(final.get("status", "")).lower()

        state[slug] = {
            "buffer_post_id": post_id,
            "buffer_status": status,
            "buffer_sent_at": final.get("sentAt"),
            "buffer_channel_id": final.get("channelId"),
            "title": title,
            "url": url,
            "source_sha": item.get("source_sha"),
            "image_url": image_url,
        }
        save_json(STATE, state)

        if status == "error":
            raise RuntimeError(
                f"Buffer created Bluesky post {post_id} for '{title}' but publishing failed."
            )
        if status != "sent":
            raise RuntimeError(
                f"Buffer created Bluesky post {post_id} for '{title}', but it did not reach "
                f"'sent' status within 90 seconds (status={status!r})."
            )

        posted += 1
        print(
            f"[bluesky-posted] {title}{' with image' if image_url else ''} "
            f"(Buffer id={post_id}, sentAt={final.get('sentAt')})"
        )

    save_json(STATE, state)
    print(f"USA Bluesky publishing complete: {posted} new post(s).")


if __name__ == "__main__":
    main()
