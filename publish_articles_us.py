from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.blogger import BloggerClient

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles-us"
STATE_PATH = ROOT / "state" / "articles_us_published.json"
USA_BLOG_HOST = "worthbuyingusa.blogspot.com"

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


def add_us_epn_tracking(content: str) -> str:
    """Ensure every eBay US href carries the Worth Buying USA EPN campaign."""

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in US_EBAY_HOSTS:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        affiliate_keys = set(US_EPN_PARAMS)
        query = [(key, value) for key, value in existing if key not in affiliate_keys]
        query.extend(US_EPN_PARAMS.items())
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        escaped_url = html.escape(tracked_url, quote=True)
        return f"href={quote}{escaped_url}{quote}"

    return HREF_RE.sub(replace, content)


def resolve_usa_blog(blogger: BloggerClient) -> None:
    """Resolve the USA blog from the authenticated Google account by URL.

    This avoids publishing failures caused by a stale or incorrect numeric
    BLOGGER_US_BLOG_ID secret while still ensuring we only target Worth Buying USA.
    """
    blogs = blogger.service.blogs().listByUser(userId="self").execute().get("items", [])

    for blog in blogs:
        url = str(blog.get("url", ""))
        host = urlsplit(url).netloc.casefold().split(":", 1)[0]
        if host == USA_BLOG_HOST:
            blogger.blog_id = str(blog["id"])
            print(f"[blog] Using {blog.get('name', 'Worth Buying USA')} ({url})")

            # Ask Blogger for the authenticated user's per-blog permissions.
            # This helps distinguish an OAuth/account problem from an API-side
            # write restriction when posts.insert returns HTTP 403.
            try:
                info = (
                    blogger.service.blogUserInfos()
                    .get(userId="self", blogId=blogger.blog_id)
                    .execute()
                )
                per_user = info.get("blog_user_info") or info.get("blogUserInfo") or {}
                print(f"[blog] API admin access: {per_user.get('hasAdminAccess')}")
            except Exception as exc:
                print(f"[blog] Could not read API admin flag: {type(exc).__name__}: {exc}")
            return

    available = ", ".join(
        f"{blog.get('name', 'Unnamed')} ({blog.get('url', 'no URL')})" for blog in blogs
    ) or "none"
    raise RuntimeError(
        "The authenticated Google account cannot see Worth Buying USA. "
        f"Blogs visible to this token: {available}. "
        "A Blogger OAuth token from an owner/admin of worthbuyingusa.blogspot.com is required."
    )


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
        content = add_us_epn_tracking(article["content_html"])
        labels = article.get("labels", [])
        mode = article.get("mode", "publish").strip().lower()

        existing = state.get(slug)
        if existing and existing.get("source_sha") == article.get("source_sha"):
            print(f"[skip] {slug}: unchanged")
            continue

        if existing and existing.get("post_id"):
            post = blogger.update_post(existing["post_id"], title, content, labels)
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
                    title,
                    content,
                    labels,
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
