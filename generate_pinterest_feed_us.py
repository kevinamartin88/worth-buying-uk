from __future__ import annotations

from src.us_targeting import prepare_us_article, us_url, localize_text, localize_html, validate_us_copy, us_audience_hours

import html
import json
import re
import subprocess
from pathlib import Path

from src.site_config import get_site_url

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles-us"
STATE_PATH = ROOT / "state" / "articles_us_published.json"
OUTPUT_PATH = ROOT / "pinterest-feed-us.xml"
IMAGE_BASE = "https://cdn.jsdelivr.net/gh/kevinamartin88/worth-buying-uk"
SITE_URL = get_site_url("us")


def xml(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def affiliate_description(value: object) -> str:
    description = " ".join(str(value or "Read the full Worth Buying USA guide.").split())
    if "affiliate" not in description.casefold():
        description = f"{description} • Affiliate"
    return description


def image_revision(image_path: Path) -> str:
    """Return the immutable commit that most recently changed an image."""
    try:
        resolved_path = image_path if image_path.is_absolute() else ROOT / image_path
        relative_path = resolved_path.relative_to(ROOT).as_posix()
        revision = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", relative_path],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError, ValueError):
        return "main"
    return revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "main"


def image_url(slug: str, image_path: Path) -> str:
    revision = image_revision(image_path)
    return f"{IMAGE_BASE}@{revision}/assets/pinterest/us/{slug}.png"


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
        image_path = ROOT / "assets" / "pinterest" / "us" / f"{slug}.png"
        if not image_path.exists():
            continue
        title = article.get("pinterest_title") or record.get("title") or slug
        title = localize_text(title)
        description = localize_text(affiliate_description(article.get("pinterest_subtitle")))
        validate_us_copy(title)
        validate_us_copy(description, social=True)
        items.append({
            "title": title,
            "description": description,
            "link": us_url(record["url"]),
            "image": image_url(slug, image_path),
                "promotion_token": str(record.get("promotion_token") or ""),
                "featured_date": str(record.get("daily_featured_date") or ""),
        })

    items.sort(key=lambda item: (item.get("featured_date", ""), item["link"]), reverse=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">',
        '  <channel>',
        '    <title>Worth Buying USA</title>',
        f'    <link>{xml(SITE_URL)}</link>',
        '    <description>Worth Buying USA buying guides, product finds and deals.</description>',
        '    <language>en-us</language>',
    ]
    for item in items:
        lines.extend([
            '    <item>',
            f'      <title>{xml(item["title"])}</title>',
            f'      <link>{xml(item["link"])}</link>',
            f'      <guid isPermaLink="true">{xml(item["link"])}</guid>',
            f'      <description>{xml(item["description"])}</description>',
            f'      <image>{xml(item["image"])}</image>',
            f'      <enclosure url="{xml(item["image"])}" type="image/png" />',
            f'      <media:content url="{xml(item["image"])}" medium="image" type="image/png" />',
            f'      <media:thumbnail url="{xml(item["image"])}" />',
            '    </item>',
        ])
    lines.extend(['  </channel>', '</rss>', ''])
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated USA Pinterest RSS feed with {len(items)} item(s): {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
