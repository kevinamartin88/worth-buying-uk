from __future__ import annotations

# Image-gated Blogger publisher.

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.article_copy import clean_article_disclosures
from src.article_images import (
    add_required_hero,
    backfill_hero_if_missing,
    verify_any_image,
    verify_required_hero,
)
from src.blogger import BloggerClient

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles-us"
STATE_PATH = ROOT / "state" / "articles_us_published.json"
USA_BLOG_HOSTS = {"www.worthbuyingusa.com", "worthbuyingusa.blogspot.com"}

US_EPN_PARAMS = {
    "mkcid": "1",
    "mkrid": "711-53200-19255-0",
    "siteid": "0",
    "campid": "5339209205",
    "toolid": "20014",
    "customid": "",
    "mkevt": "1",
}
US_EBAY_HOSTS = {"ebay.com", "www.ebay.com"}
US_AMAZON_HOSTS = {"amazon.com", "www.amazon.com"}
US_AMAZON_TAG = "worthbuyingus-20"
HREF_RE = re.compile(r'href=(["\'])(https?://[^"\']+)\1', re.IGNORECASE)


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


def add_us_epn_tracking(content: str, custom_id: str = "") -> str:
    """Ensure every eBay US href carries the Worth Buying USA EPN campaign."""

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in US_EBAY_HOSTS:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        tracking_params = {**US_EPN_PARAMS, "customid": custom_id[:256]}
        affiliate_keys = set(tracking_params)
        query = [(key, value) for key, value in existing if key not in affiliate_keys]
        query.extend(tracking_params.items())
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        escaped_url = html.escape(tracked_url, quote=True)
        return f"href={quote}{escaped_url}{quote}"

    return HREF_RE.sub(replace, content)


def add_us_amazon_tracking(content: str) -> str:
    """Ensure every Amazon US href carries the Worth Buying USA Associates tag."""

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in US_AMAZON_HOSTS:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        query = [(key, value) for key, value in existing if key.casefold() != "tag"]
        query.append(("tag", US_AMAZON_TAG))
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        return f"href={quote}{html.escape(tracked_url, quote=True)}{quote}"

    return HREF_RE.sub(replace, content)


def resolve_usa_blog(blogger: BloggerClient) -> None:
    blogger.resolve_blog(USA_BLOG_HOSTS, "Worth Buying USA")


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
        print("No US articles directory found.")
        return

    state = load_state()
    blogger = BloggerClient.from_env()
    resolve_usa_blog(blogger)

    for path in sorted(ARTICLES_DIR.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        slug = article["slug"]
        title = article["title"]
        article_content = clean_article_disclosures(
            add_us_amazon_tracking(
                add_us_epn_tracking(article["content_html"], custom_id=slug)
            )
        )
        content, hero_url = add_required_hero(
            article_content,
            market="us",
            slug=slug,
            title=title,
        )
        labels = article.get("labels", [])
        mode = article.get("mode", "publish").strip().lower()
        promotion = article.get("_promotion") or {}
        promotion_token = str(promotion.get("promotion_token") or "").strip()
        feature_today = bool(
            promotion_token
            and promotion.get("return_to_top")
            and promotion.get("is_refresh")
        )

        # Keep the historical USA fingerprint based on the article body alone.
        # The mandatory hero is verified independently so legacy state remains
        # stable while image-less API posts can be safely repaired.
        fingerprint = publish_fingerprint(article, article_content)

        existing = state.get(slug)
        current_post = None
        if existing and existing.get("post_id"):
            current_post = blogger.get_post_or_none(str(existing["post_id"]))
            if current_post is None:
                found_by_title = blogger.find_post_by_exact_title(title)
                if found_by_title and found_by_title.get("id"):
                    existing["post_id"] = str(found_by_title["id"])
                    current_post = blogger.get_post(str(found_by_title["id"]))
                    print(
                        f"[state-repaired] USA {slug}: replaced stale Blogger post ID "
                        f"with {found_by_title['id']}"
                    )
                else:
                    print(
                        f"[state-stale] USA {slug}: no live post matched the saved state; "
                        "treating it as unpublished."
                    )
                    existing = None

        if existing and existing.get("publish_fingerprint") == fingerprint and current_post:
            post = current_post
            repaired_content, hero_url, repaired = backfill_hero_if_missing(
                str(post.get("content", "")),
                market="us",
                slug=slug,
                title=title,
            )
            if repaired:
                post = blogger.update_post_content(str(existing["post_id"]), repaired_content)
                stored = blogger.get_post(str(existing["post_id"]))
                verify_required_hero(str(stored.get("content", "")), hero_url, title)
                print(f"[image-backfilled] {title}: required USA hero image added")
            else:
                verify_any_image(str(post.get("content", "")), title)
                print(f"[skip] {slug}: unchanged and image already present")

            existing["hero_image_url"] = hero_url
            existing["image_required"] = True
            if feature_today and existing.get("promotion_token") != promotion_token:
                featured = blogger.feature_post_today(str(existing["post_id"]))
                existing["url"] = featured.get("url") or existing.get("url")
                existing["promotion_token"] = promotion_token
                existing["daily_featured_date"] = promotion.get("daily_featured_date")
                print(f"[daily-feature-refresh] {title}: moved back to top of Blogger")
            continue

        body_replaced = False
        if existing and current_post:
            post = blogger.update_post(str(existing["post_id"]), title, content, labels)
            action = "updated"
            body_replaced = True
            if mode == "publish" and existing.get("status") != "published":
                post = blogger.publish_post(str(existing["post_id"]))
        else:
            found = blogger.find_post_by_exact_title(title)
            if found and found.get("id"):
                post_id = str(found["id"])
                post = blogger.get_post(post_id)
                repaired_content, hero_url, repaired = backfill_hero_if_missing(
                    str(post.get("content", "")),
                    market="us",
                    slug=slug,
                    title=title,
                )
                if repaired:
                    post = blogger.update_post_content(post_id, repaired_content)
                    action = "reconciled-image-backfilled"
                else:
                    action = "reconciled"
                if mode == "publish" and str(found.get("status", "")).upper() != "LIVE":
                    post = blogger.publish_post(post_id)
            else:
                try:
                    post = blogger.create_post(
                        title,
                        content,
                        labels,
                        is_draft=(mode != "publish"),
                    )
                except Exception:
                    print(f"[blogger-error] Could not create USA article: {title}")
                    raise
                action = "created"
                body_replaced = True

        stored = blogger.get_post(str(post["id"]))
        if (
            feature_today
            and existing
            and existing.get("promotion_token") != promotion_token
        ):
            stored = blogger.feature_post_today(str(stored["id"]))
            print(f"[daily-feature-refresh] {title}: moved back to top of Blogger")
        if body_replaced:
            verify_required_hero(str(stored.get("content", "")), hero_url, title)
            print(f"[verified] {title}: required USA hero image stored by Blogger")
        else:
            verify_any_image(str(stored.get("content", "")), title)
            print(f"[verified] {title}: Blogger article image present")

        state[slug] = {
            "post_id": stored["id"],
            "url": stored.get("url") or post.get("url"),
            "title": title,
            "status": "published" if mode == "publish" else "draft",
            "source_sha": article.get("source_sha"),
            "publish_fingerprint": fingerprint,
            "source_file": path.name,
            "hero_image_url": hero_url,
            "image_required": True,
            "promotion_token": promotion_token or None,
            "daily_featured_date": promotion.get("daily_featured_date"),
        }
        print(f"[{action}] {title} ({state[slug]['status']})")

    save_state(state)


if __name__ == "__main__":
    main()
