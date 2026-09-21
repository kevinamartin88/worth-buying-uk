from __future__ import annotations

import html
import json
import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from src.site_config import get_site_config, get_site_url

ROOT = Path(__file__).resolve().parent
EMAIL_STATE_PATH = ROOT / "state" / "email_published.json"

UK_EPN_PARAMS = {
    "mkcid": "1",
    "mkrid": "710-53481-19255-0",
    "siteid": "3",
    "campid": "5339209132",
    "toolid": "20014",
    "customid": "",
    "mkevt": "1",
}
US_EPN_PARAMS = {
    "mkcid": "1",
    "mkrid": "711-53200-19255-0",
    "siteid": "0",
    "campid": "5339209205",
    "toolid": "20014",
    "customid": "",
    "mkevt": "1",
}

UK_EBAY_HOSTS = {"ebay.co.uk", "www.ebay.co.uk"}
US_EBAY_HOSTS = {"ebay.com", "www.ebay.com"}
HREF_RE = re.compile(r'href=(["\\\'])(https?://[^"\\\']+)\\1', re.IGNORECASE)
ANCHOR_OPEN_RE = re.compile(
    r'(<a\\b[^>]*href=(["\\\'])(https?://[^"\\\']+)\\2[^>]*)(>)',
    re.IGNORECASE,
)


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


def add_epn_tracking(content: str, market: str) -> str:
    params = UK_EPN_PARAMS if market == "uk" else US_EPN_PARAMS
    hosts = UK_EBAY_HOSTS if market == "uk" else US_EBAY_HOSTS

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in hosts:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        affiliate_keys = set(params)
        query = [(key, value) for key, value in existing if key not in affiliate_keys]
        query.extend(params.items())
        tracked_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
        return f"href={quote}{html.escape(tracked_url, quote=True)}{quote}"

    return HREF_RE.sub(replace, content)


def style_retailer_buttons(content: str) -> str:
    """Render eBay and Amazon affiliate links as matching CTA buttons."""

    retailer_hosts = {
        "ebay.co.uk",
        "www.ebay.co.uk",
        "ebay.com",
        "www.ebay.com",
        "amazon.co.uk",
        "www.amazon.co.uk",
        "amazon.com",
        "www.amazon.com",
    }
    button_style = (
        "display:inline-block;padding:11px 16px;margin:6px 8px 6px 0;"
        "background:#0f766e;color:#ffffff;text-decoration:none;"
        "font-weight:700;border-radius:7px;line-height:1.25;"
    )

    def replace(match: re.Match[str]) -> str:
        opening = match.group(1)
        raw_url = html.unescape(match.group(3))
        host = urlsplit(raw_url).netloc.casefold().split(":", 1)[0]
        if host not in retailer_hosts:
            return match.group(0)
        if re.search(r"\\bstyle\\s*=", opening, re.IGNORECASE):
            return match.group(0)
        return f'{opening} style="{button_style}">'

    return ANCHOR_OPEN_RE.sub(replace, content)


def hero_image_html(slug: str, title: str, market: str) -> str:
    if market == "uk":
        image_path = ROOT / "assets" / "pinterest" / f"{slug}.png"
        image_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/{slug}.png"
        )
    else:
        image_path = ROOT / "assets" / "pinterest" / "us" / f"{slug}.png"
        image_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/us/{slug}.png"
        )

    if not image_path.exists():
        return ""

    alt = html.escape(title, quote=True)
    return (
        f'<p style="text-align:center;"><img src="{image_url}" alt="{alt}" '
        'style="width:100%;max-width:460px;height:auto;display:block;'
        'margin:0 auto 24px auto;" /></p>\n'
    )


def send_email(subject: str, html_content: str, to_address: str) -> None:
    smtp_email = os.environ["SMTP_EMAIL"]
    smtp_password = os.environ["SMTP_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_email
    msg["To"] = to_address
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, [to_address], msg.as_string())


def find_public_post_url(site_url: str, title: str) -> str | None:
    feed_url = f"{site_url.rstrip('/')}/feeds/posts/default?alt=json&max-results=50"
    req = Request(feed_url, headers={"User-Agent": "WorthBuyingPublisher/1.0"})
    with urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = payload.get("feed", {}).get("entry", [])
    wanted = " ".join(title.split())
    for entry in entries:
        entry_title = " ".join(str(entry.get("title", {}).get("$t", "")).split())
        if entry_title != wanted:
            continue
        for link in entry.get("link", []):
            if link.get("rel") == "alternate" and link.get("href"):
                return str(link["href"])
    return None


def canonicalize_url(url: str, public_site_url: str) -> str:
    source = urlsplit(url)
    public = urlsplit(public_site_url)
    return urlunsplit(
        (public.scheme, public.netloc, source.path, source.query, source.fragment)
    )


def resolve_public_url(
    lookup_urls: list[str],
    public_site_url: str,
    title: str,
    attempts: int = 12,
) -> str | None:
    for attempt in range(1, attempts + 1):
        for lookup_url in lookup_urls:
            try:
                url = find_public_post_url(lookup_url, title)
                if url:
                    return canonicalize_url(url, public_site_url)
            except Exception as exc:
                print(
                    f"[wait] Could not read Blogger feed at {lookup_url}: "
                    f"{type(exc).__name__}: {exc}"
                )
        if attempt < attempts:
            print(f"[wait] Waiting for Blogger to publish '{title}' ({attempt}/{attempts})")
            time.sleep(10)
    return None


def main() -> None:
    market = os.getenv("MARKET", "uk").strip().lower()
    if market not in {"uk", "us"}:
        raise ValueError("MARKET must be 'uk' or 'us'")

    site_config = get_site_config(market)
    public_site_url = get_site_url(market).rstrip("/")
    blogspot_url = str(site_config["blogspot_url"]).rstrip("/")
    lookup_urls = list(dict.fromkeys([public_site_url, blogspot_url]))

    if market == "uk":
        articles_dir = ROOT / "articles"
        target_email = os.environ["BLOGGER_UK_EMAIL_POST_ADDRESS"]
        blog_state_path = ROOT / "state" / "articles_published.json"
    else:
        articles_dir = ROOT / "articles-us"
        target_email = os.environ["BLOGGER_US_EMAIL_POST_ADDRESS"]
        blog_state_path = ROOT / "state" / "articles_us_published.json"

    if not articles_dir.exists():
        print(f"No article directory found: {articles_dir}")
        return

    email_state = load_json(EMAIL_STATE_PATH)
    blog_state = load_json(blog_state_path)

    for path in sorted(articles_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        mode = str(article.get("mode", "publish")).strip().lower()
        if mode != "publish":
            print(f"[skip] {path.name}: not marked for publish")
            continue

        slug = article["slug"]
        title = article["title"]
        source_sha = article.get("source_sha")
        state_key = f"{market}:{slug}"

        # Mail2Blogger is a create-only fallback. Never email an article that
        # already exists in the normal Blogger publication state, otherwise an
        # edit could accidentally create a duplicate public post.
        existing_blog = blog_state.get(slug)
        if existing_blog and existing_blog.get("status") == "published":
            print(f"[skip] {slug}: already exists on Blogger")
            continue

        emailed = email_state.get(state_key)
        if not emailed:
            content = hero_image_html(slug, title, market) + style_retailer_buttons(
                add_epn_tracking(article["content_html"], market)
            )
            send_email(
                subject=title,
                html_content=content,
                to_address=target_email,
            )
            email_state[state_key] = {
                "title": title,
                "source_sha": source_sha,
                "source_file": path.name,
                "market": market,
                "sent": True,
            }
            save_json(EMAIL_STATE_PATH, email_state)
            print(f"[sent] {title}")
        else:
            print(f"[resolve] {slug}: email already sent; checking public Blogger feed")

        url = resolve_public_url(lookup_urls, public_site_url, title)
        if not url:
            print(
                f"[warning] Blogger email was sent for '{title}', but its public URL "
                "could not yet be resolved. A later workflow run will retry without "
                "sending the email again."
            )
            continue

        blog_state[slug] = {
            "post_id": None,
            "url": url,
            "title": title,
            "status": "published",
            "source_sha": source_sha,
            "source_file": path.name,
            "publisher": "email",
        }
        save_json(blog_state_path, blog_state)
        email_state[state_key]["url"] = url
        save_json(EMAIL_STATE_PATH, email_state)
        print(f"[published] {title}: {url}")


if __name__ == "__main__":
    main()
