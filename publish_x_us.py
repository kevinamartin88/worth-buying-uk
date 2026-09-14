from __future__ import annotations

import json
import os
from pathlib import Path

from src.buffer import BufferClient


ROOT = Path(__file__).resolve().parent
BLOG_STATE = ROOT / "state" / "articles_us_published.json"
X_STATE = ROOT / "state" / "x_us_published.json"


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


def default_x_text(title: str, url: str) -> str:
    suffix = f"\n\nAd/Affiliate 🔗 {url}"
    intro = "New on Worth Buying USA: "
    max_title = 280 - len(intro) - len(suffix)
    if max_title < 20:
        max_title = 20
    clean_title = " ".join(title.split())
    if len(clean_title) > max_title:
        clean_title = clean_title[: max_title - 1].rstrip() + "…"
    return f"{intro}{clean_title}{suffix}"


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

        article_path = ROOT / "articles-us" / item.get("source_file", "")
        x_text = None
        if article_path.exists():
            try:
                article = json.loads(article_path.read_text(encoding="utf-8"))
                x_text = article.get("x_text")
            except (OSError, json.JSONDecodeError):
                pass

        text = x_text.strip() if isinstance(x_text, str) and x_text.strip() else default_x_text(title, url)
        post = buffer.create_post(text=text, mode="shareNow")
        x_state[slug] = {
            "buffer_post_id": post.get("id"),
            "title": title,
            "url": url,
            "source_sha": item.get("source_sha"),
        }
        posted += 1
        print(f"[posted] {title}")

    save_json(X_STATE, x_state)
    print(f"USA X publishing complete: {posted} new post(s).")


if __name__ == "__main__":
    main()
