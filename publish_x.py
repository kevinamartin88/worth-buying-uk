from __future__ import annotations

import json
import os
from pathlib import Path

from requests.exceptions import HTTPError

from src.buffer import BufferClient


ROOT = Path(__file__).resolve().parent
BLOG_STATE = ROOT / "state" / "articles_published.json"
X_STATE = ROOT / "state" / "x_published.json"
AI_IMAGE_DIR = ROOT / "assets" / "ai" / "uk"
AI_IMAGE_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/ai/uk"
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
        f"Affiliate 🔗 {url}\n"
        f"{hashtags}"
    )
    if len(text) <= 280:
        return text

    suffix = f"\n\nAffiliate 🔗 {url}\n{hashtags}"
    prefix = f"{emoji} {hook}\n\n"
    available = 280 - len(prefix) - len(suffix)
    short_title = clean_title[: max(20, available - 1)].rstrip() + "…"
    return f"{prefix}{short_title}{suffix}"


def custom_x_text(template: str, title: str, url: str) -> str:
    normalized = (
        template.replace("Ad/Affiliate", "Affiliate")
        .replace("Ad / Affiliate", "Affiliate")
        .replace("AD/Affiliate", "Affiliate")
    )
    text = normalized.format(title=title, url=url).strip()
    if len(text) <= 280:
        return text
    suffix = f"\nAffiliate 🔗 {url}"
    body = text.replace(suffix, "").strip()
    max_body = max(40, 280 - len(suffix) - 1)
    return body[: max_body - 1].rstrip() + "…" + suffix


def main() -> None:
    if not os.getenv("BUFFER_API_KEY"):
        print("[skip] BUFFER_API_KEY is not configured")
        return

    blog_state = load_json(BLOG_STATE)
    x_state = load_json(X_STATE)

    pending = []
    for slug, item in sorted(blog_state.items()):
        if item.get("status") != "published":
            continue
        if not item.get("url") or not item.get("title"):
            continue
        if slug in x_state:
            continue
        pending.append((slug, item))

    if not pending:
        print("[skip] No new UK articles need X publishing; Buffer API was not called.")
        return

    buffer = BufferClient.from_env()
    try:
        buffer.find_x_channel_id()
    except HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            print("[rate-limit] Buffer returned HTTP 429. UK X publishing will retry on the next reconciliation run.")
            return
        raise

    posted = 0

    for slug, item in pending:
        url = item["url"]
        title = item["title"]

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

        ai_image_path = AI_IMAGE_DIR / f"{slug}.jpg"
        fallback_image_path = X_IMAGE_DIR / f"{slug}.png"
        if ai_image_path.exists():
            image_url = f"{AI_IMAGE_BASE}/{slug}.jpg"
        elif fallback_image_path.exists():
            image_url = f"{X_IMAGE_BASE}/{slug}.png"
        else:
            image_url = None

        try:
            created = buffer.create_post(text=text, mode="shareNow", image_url=image_url)
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                print("[rate-limit] Buffer returned HTTP 429. UK X publishing will retry on the next reconciliation run.")
                save_json(X_STATE, x_state)
                return
            raise

        post_id = str(created["id"])
        x_state[slug] = {
            "buffer_post_id": post_id,
            "buffer_status": str(created.get("status", "submitted")).lower(),
            "buffer_sent_at": created.get("sentAt"),
            "buffer_channel_id": created.get("channelId"),
            "title": title,
            "url": url,
            "source_sha": item.get("source_sha"),
            "image_url": image_url,
        }
        save_json(X_STATE, x_state)

        try:
            final = buffer.wait_for_post(post_id, timeout_seconds=90)
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                print(
                    f"[rate-limit] Buffer accepted '{title}' (id={post_id}) but rate-limited status checks. "
                    "The workflow will not fail or duplicate the post."
                )
                return
            raise

        status = str(final.get("status", "")).lower()
        x_state[slug]["buffer_status"] = status
        x_state[slug]["buffer_sent_at"] = final.get("sentAt")
        x_state[slug]["buffer_channel_id"] = final.get("channelId")
        save_json(X_STATE, x_state)

        if status == "error":
            raise RuntimeError(
                f"Buffer created post {post_id} for '{title}' but X publishing failed."
            )
        if status != "sent":
            raise RuntimeError(
                f"Buffer created post {post_id} for '{title}', but it did not reach "
                f"'sent' status within 90 seconds (status={status!r})."
            )

        posted += 1
        print(
            f"[posted-and-verified] {title}{' with image' if image_url else ''} "
            f"(Buffer id={post_id}, sentAt={final.get('sentAt')})"
        )

    save_json(X_STATE, x_state)
    print(f"X publishing complete: {posted} new post(s).")


if __name__ == "__main__":
    main()
