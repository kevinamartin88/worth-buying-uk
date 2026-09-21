from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.blogger import BloggerClient


ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
STATE_PATH = ROOT / "state" / "articles_published.json"
PINTEREST_DIR = ROOT / "assets" / "pinterest"
RAW_BASE = "https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/assets/pinterest"

UK_EPN_CAMPAIGN_ID = "5339209132"
UK_EPN_PARAMS = {
    "mkcid": "1",
    "mkrid": "710-53481-19255-0",
    "siteid": "3",
    "campid": UK_EPN_CAMPAIGN_ID,
    "toolid": "20014",
    "customid": "",
    "mkevt": "1",
}
UK_EBAY_HOSTS = {"ebay.co.uk", "www.ebay.co.uk"}
UK_AMAZON_HOSTS = {"amazon.co.uk", "www.amazon.co.uk"}
UK_AMAZON_TAG = "worthbuyin008-21"
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


def add_uk_epn_tracking(content: str) -> str:
    """Ensure every eBay UK href carries the Worth Buying UK EPN campaign."""

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in UK_EBAY_HOSTS:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        affiliate_keys = set(UK_EPN_PARAMS)
        query = [(key, value) for key, value in existing if key not in affiliate_keys]
        query.extend(UK_EPN_PARAMS.items())
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        escaped_url = html.escape(tracked_url, quote=True)
        return f"href={quote}{escaped_url}{quote}"

    return HREF_RE.sub(replace, content)


def add_uk_amazon_tracking(content: str) -> str:
    """Ensure every Amazon UK href carries the Worth Buying UK Associates tag."""

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in UK_AMAZON_HOSTS:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        query = [(key, value) for key, value in existing if key.casefold() != "tag"]
        query.append(("tag", UK_AMAZON_TAG))
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        return f"href={quote}{html.escape(tracked_url, quote=True)}{quote}"

    return HREF_RE.sub(replace, content)


def count_ebay_links(content: str) -> int:
    count = 0
    for match in HREF_RE.finditer(content):
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host in UK_EBAY_HOSTS:
            count += 1
    return count


def verify_uk_epn_tracking(content: str) -> None:
    ebay_links = count_ebay_links(content)
    if ebay_links == 0:
        return
    tracked = content.count(f"campid={UK_EPN_CAMPAIGN_ID}") + content.count(f"campid%3D{UK_EPN_CAMPAIGN_ID}")
    if tracked < ebay_links:
        raise RuntimeError(
            f"EPN verification failed: found {ebay_links} eBay UK link(s) but only {tracked} "
            f"link(s) contained campaign {UK_EPN_CAMPAIGN_ID}."
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
        'style="width:460px;max-width:100%;height:auto;display:block;margin:0 auto 24px auto;" /></p>\n'
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
        article_content = add_uk_amazon_tracking(
            add_uk_epn_tracking(article["content_html"])
        )
        content = pinterest_image_html(article) + article_content
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

        # Blogger's create/update response includes the stored post content. Verifying
        # that response avoids a second API read and still confirms the published
        # payload contains the correct campaign tracking.
        verify_uk_epn_tracking(str(post.get("content", content)))
        print(f"[verified] {title}: UK EPN campaign {UK_EPN_CAMPAIGN_ID}")

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
