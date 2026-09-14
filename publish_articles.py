from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from src.blogger import BloggerClient


ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
STATE_PATH = ROOT / "state" / "articles_published.json"
PINTEREST_DIR = ROOT / "assets" / "pinterest"
RAW_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/pinterest"


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def pinterest_image_html(article: dict) -> str:
    if article.get("pinterest_enabled", True) is False:
        return ""
    slug = article["slug"]
    image_path = PINTEREST_DIR / f"{slug}.png"
    if not image_path.exists():
        return ""
    image_url = f"{RAW_BASE}/{slug}.png"
    alt = html.escape(str(article.get("pinterest_title") or article["title"]), quote=True)
    return (
        f'<p><img src="{image_url}" alt="{alt}" '
        'style="max-width:100%;height:auto;display:block;margin:0 auto 24px auto;" /></p>\n'
    )


def publish_fingerprint(article: dict, content: str) -> str:
    payload = {
        "title": article["title"],
        "content": content,
        "labels": article.get("labels", []),
        "mode": article.get("mode", "publish").strip().lower(),
        "source_sha": article.get("source_sha"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    if not ARTICLES_DIR.exists():
        print("No articles directory found.")
        return

    state = load_state()
    blogger = BloggerClient.from_env()

    for path in sorted(ARTICLES_DIR.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        slug = article["slug"]
        title = article["title"]
        content = pinterest_image_html(article) + article["content_html"]
        labels = article.get("labels", [])
        mode = article.get("mode", "publish").strip().lower()
        fingerprint = publish_fingerprint(article, content)

        existing = state.get(slug)
        if existing and existing.get("publish_fingerprint") == fingerprint:
            print(f"[skip] {slug}: unchanged")
            continue

        if existing and existing.get("post_id"):
            post = blogger.update_post(
                post_id=existing["post_id"],
                title=title,
                content=content,
                labels=labels,
            )
            action = "updated"
            if mode == "publish" and existing.get("status") != "published":
                post = blogger.publish_post(existing["post_id"])
        else:
            found = blogger.find_post_by_exact_title(title)
            if found and found.get("id"):
                post_id = found["id"]
                post = blogger.update_post(post_id, title, content, labels)
                action = "reconciled"
                if mode == "publish" and str(found.get("status", "")).upper() != "LIVE":
                    post = blogger.publish_post(post_id)
            else:
                post = blogger.create_post(
                    title=title,
                    content=content,
                    labels=labels,
                    is_draft=(mode != "publish"),
                )
                action = "created"

        state[slug] = {
            "post_id": post["id"],
            "url": post.get("url"),
            "title": title,
            "status": "published" if mode == "publish" else "draft",
            "source_sha": article.get("source_sha"),
            "publish_fingerprint": fingerprint,
            "source_file": path.name,
        }
        print(f"[{action}] {title} ({state[slug]['status']})")

    save_state(state)


if __name__ == "__main__":
    main()
