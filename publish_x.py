from __future__ import annotations

import json
import os
from pathlib import Path

from src.buffer import BufferClient


ROOT = Path(__file__).resolve().parent
BLOG_STATE = ROOT / "state" / "articles_published.json"
X_STATE = ROOT / "state" / "x_published.json"
X_IMAGE_DIR = ROOT / "assets" / "x" / "uk"
X_IMAGE_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/x/uk"


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


def category_style(labels: list[str]) -> tuple[str, str, str]:
    lowered = {str(label).casefold() for label in labels}
    if {"kitchen", "home", "appliances"} & lowered:
        return "🏠", "Small upgrades can make a surprisingly big difference.", "#Home #Kitchen"
    if {"gaming", "playstation"} & lowered:
        return "🎮", "Buying gaming gear? The best value is not always the newest model.", "#Gaming #PlayStation"
    if {"jewellery", "jewelry"} & lowered:
        return "💎", "Jewellery deals can look great on paper — the details matter.", "#Jewellery #Shopping"
    if {"garage tools", "motoring", "workshop equipment"} & lowered:
        return "🔧", "Workshop gear is worth buying carefully, especially when safety is involved.", "#Tools #Motoring"
    if {"apple", "samsung", "technology", "tech", "wearables"} & lowered:
        return "📱", "Before paying full price for tech, check what actually matters in day-to-day use.", "#Tech #BuyingGuide"
    return "🔎", "Worth buying, or worth skipping? Here are the practical checks that matter.", "#Shopping #BuyingGuide"


def default_x_text(title: str, url: str, labels: list[str]) -> str:
    emoji, hook, hashtags = category_style(labels)
    clean_title = " ".join(title.split())
    text = (
        f"{emoji} {hook}\n\n"
        f"{clean_title}\n\n"
        f"Our guide focuses on value, usability and what to check before you buy.\n\n"
        f"Ad/Affiliate 🔗 {url}\n"
        f"{hashtags}"
    )
    if len(text) <= 280:
        return text

    suffix = f"\n\nAd/Affiliate 🔗 {url}\n{hashtags}"
    prefix = f"{emoji} {hook}\n\n"
    available = 280 - len(prefix) - len(suffix)
    short_title = clean_title[: max(20, available - 1)].rstrip() + "…"
    return f"{prefix}{short_title}{suffix}"


def custom_x_text(template: str, title: str, url: str) -> str:
    text = template.format(title=title, url=url).strip()
    if len(text) <= 280:
        return text
    suffix = f"\nAd/Affiliate 🔗 {url}"
    body = text.replace(suffix, "").strip()
    max_body = max(40, 280 - len(suffix) - 1)
    return body[: max_body - 1].rstrip() + "…" + suffix


def main() -> None:
    if not os.getenv("BUFFER_API_KEY"):
        print("[skip] BUFFER_API_KEY is not configured")
        return

    blog_state = load_json(BLOG_STATE)
    x_state = load_json(X_STATE)
    buffer = BufferClient.from_env()

    posted = 0
    for slug, item in sorted(blog_state.items()):
        if item.get("status") != "published":
            continue
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue
        if slug in x_state:
            continue

        article_path = ROOT / "articles" / item.get("source_file", "")
        article: dict = {}
        if article_path.exists():
            try:
                article = json.loads(article_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                article = {}

        template = article.get("x_text")
        if isinstance(template, str) and template.strip():
            text = custom_x_text(template, title, url)
        else:
            text = default_x_text(title, url, list(article.get("labels", [])))

        image_path = X_IMAGE_DIR / f"{slug}.png"
        image_url = f"{X_IMAGE_BASE}/{slug}.png" if image_path.exists() else None
        post = buffer.create_post(text=text, mode="shareNow", image_url=image_url)
        x_state[slug] = {
            "buffer_post_id": post.get("id"),
            "title": title,
            "url": url,
            "source_sha": item.get("source_sha"),
            "image_url": image_url,
        }
        posted += 1
        print(f"[posted] {title}{' with image' if image_url else ''}")

    save_json(X_STATE, x_state)
    print(f"X publishing complete: {posted} new post(s).")


if __name__ == "__main__":
    main()
