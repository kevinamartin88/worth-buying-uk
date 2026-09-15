from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
STATE_PATH = ROOT / "state" / "articles_published.json"
OUTPUT_PATH = ROOT / "pinterest-feed.xml"
IMAGE_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/pinterest"
SITE_URL = "https://worthbuyinguk.blogspot.com/"


def xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    state = load_json(STATE_PATH)
    items: list[dict] = []

    for slug, record in state.items():
        if record.get("status") != "published" or not record.get("url"):
            continue

        article_path = ARTICLES_DIR / str(record.get("source_file", f"{slug}.json"))
        article = load_json(article_path)
        if article.get("pinterest_enabled", True) is False:
            continue

        image_path = ROOT / "assets" / "pinterest" / f"{slug}.png"
        if not image_path.exists():
            continue

        title = article.get("pinterest_title") or record.get("title") or slug
        description = article.get("pinterest_subtitle") or "Read the full Worth Buying UK guide."
        items.append(
            {
                "title": title,
                "description": description,
                "link": record["url"],
                "image": f"{IMAGE_BASE}/{slug}.png",
            }
        )

    # Stable ordering prevents normal reruns from constantly changing the feed.
    items.sort(key=lambda item: item["link"], reverse=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">',
        '  <channel>',
        '    <title>Worth Buying UK</title>',
        f'    <link>{xml(SITE_URL)}</link>',
        '    <description>Worth Buying UK buying guides, product finds and deals.</description>',
        '    <language>en-gb</language>',
    ]

    for item in items:
        lines.extend(
            [
                '    <item>',
                f'      <title>{xml(item["title"])}</title>',
                f'      <link>{xml(item["link"])}</link>',
                f'      <guid isPermaLink="true">{xml(item["link"])}</guid>',
                f'      <description>{xml(item["description"])}</description>',
                f'      <enclosure url="{xml(item["image"])}" type="image/png" />',
                f'      <media:content url="{xml(item["image"])}" medium="image" type="image/png" />',
                '    </item>',
            ]
        )

    lines.extend(['  </channel>', '</rss>', ''])
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated Pinterest RSS feed with {len(items)} item(s): {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
