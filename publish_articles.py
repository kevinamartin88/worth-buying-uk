from __future__ import annotations

import json
from pathlib import Path

from src.blogger import BloggerClient


ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
STATE_PATH = ROOT / "state" / "articles_published.json"


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
        content = article["content_html"]
        labels = article.get("labels", [])
        mode = article.get("mode", "publish").strip().lower()

        existing = state.get(slug)
        if existing and existing.get("source_sha") == article.get("source_sha"):
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
            "source_file": path.name,
        }
        print(f"[{action}] {title} ({state[slug]['status']})")

    save_state(state)


if __name__ == "__main__":
    main()
