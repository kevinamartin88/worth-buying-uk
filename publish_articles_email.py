from __future__ import annotations

import html
import json
import os
import re
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from src.site_config import get_site_config, get_site_url

ROOT = Path(__file__).resolve().parent
EMAIL_STATE_PATH = ROOT / "state" / "email_published.json"
EMAIL_RETRY_AFTER_HOURS = 6
EMAIL_MAX_SEND_ATTEMPTS = 2

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
UK_AMAZON_HOSTS = {"amazon.co.uk", "www.amazon.co.uk"}
US_AMAZON_HOSTS = {"amazon.com", "www.amazon.com"}
UK_AMAZON_TAG = "worthbuyin008-21"
US_AMAZON_TAG = "worthbuyingus-20"
HREF_RE = re.compile(r'href=(["\\\'])(https?://[^"\\\']+)\\1', re.IGNORECASE)
ANCHOR_OPEN_RE = re.compile(
    r'(<a\\b[^>]*href=(["\\\'])(https?://[^"\\\']+)\\2[^>]*)(>)',
    re.IGNORECASE,
)
FULL_ANCHOR_RE = re.compile(
    r'(<a\\b[^>]*href=(["\\\'])(https?://[^"\\\']+)\\2[^>]*>.*?</a>)',
    re.IGNORECASE | re.DOTALL,
)

PRIMARY_CATEGORIES = ("Tech", "Home & Kitchen", "Motoring", "Gaming", "Deals")
CATEGORY_ALIASES = {
    "tech": "Tech",
    "technology": "Tech",
    "apple": "Tech",
    "samsung": "Tech",
    "wearables": "Tech",
    "smartphones": "Tech",
    "phones": "Tech",
    "laptops": "Tech",
    "tablets": "Tech",
    "refurbished": "Tech",
    "home": "Home & Kitchen",
    "kitchen": "Home & Kitchen",
    "appliances": "Home & Kitchen",
    "cookware": "Home & Kitchen",
    "motoring": "Motoring",
    "cars": "Motoring",
    "car accessories": "Motoring",
    "auto": "Motoring",
    "auto accessories": "Motoring",
    "garage tools": "Motoring",
    "workshop equipment": "Motoring",
    "gaming": "Gaming",
    "playstation": "Gaming",
    "xbox": "Gaming",
    "nintendo": "Gaming",
    "deals": "Deals",
    "ebay deals": "Deals",
}


def primary_category(article: dict) -> str:
    explicit = " ".join(str(article.get("primary_category", "")).split())
    if explicit in PRIMARY_CATEGORIES:
        return explicit

    labels = [" ".join(str(label).split()) for label in article.get("labels", [])]
    for label in labels:
        mapped = CATEGORY_ALIASES.get(label.casefold())
        if mapped:
            return mapped

    title = str(article.get("title", "")).casefold()
    for alias, mapped in CATEGORY_ALIASES.items():
        if alias in title:
            return mapped

    return "Deals"


def category_marker_html(category: str, public_site_url: str) -> str:
    query = urlencode({"q": category})
    href = f"{public_site_url.rstrip('/')}/search?{query}"
    safe_category = html.escape(category)
    safe_href = html.escape(href, quote=True)
    return (
        '<div class="wb-article-category" '
        'style="margin:0 0 16px 0;text-align:left;">'
        f'<a href="{safe_href}" rel="tag" '
        'style="display:inline-block;background:#edf7f6;color:#0f766e;'
        'border:1px solid #cde8e5;border-radius:999px;padding:6px 11px;'
        'font-size:12px;font-weight:800;letter-spacing:.35px;'
        'text-decoration:none;">'
        f'{safe_category}</a></div>\n'
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def email_retry_due(record: dict | None, delivery_mode: str) -> bool:
    # Manual-review emails are intentionally sent once per source version. We do
    # not want a scheduled reconciliation run repeatedly emailing the same draft.
    if delivery_mode == "manual":
        return False
    if not record or record.get("url"):
        return False

    attempts = int(record.get("send_attempts", 1 if record.get("sent") else 0))
    if attempts >= EMAIL_MAX_SEND_ATTEMPTS:
        return False

    last_sent_at = str(record.get("last_sent_at", "")).strip()
    if not last_sent_at:
        return False

    try:
        sent_at = datetime.fromisoformat(last_sent_at.replace("Z", "+00:00"))
    except ValueError:
        return False

    return datetime.now(timezone.utc) - sent_at >= timedelta(hours=EMAIL_RETRY_AFTER_HOURS)


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


def add_amazon_search_alternatives(content: str, market: str) -> str:
    """Add a matching Amazon search button beside each eBay search link."""

    ebay_hosts = UK_EBAY_HOSTS if market == "uk" else US_EBAY_HOSTS
    amazon_hosts = UK_AMAZON_HOSTS if market == "uk" else US_AMAZON_HOSTS
    amazon_base = "https://www.amazon.co.uk/s" if market == "uk" else "https://www.amazon.com/s"
    amazon_label = "Compare on Amazon UK" if market == "uk" else "Compare on Amazon"

    # Respect any Amazon links already supplied for the same search term.
    existing_amazon_queries: set[str] = set()
    for anchor_match in FULL_ANCHOR_RE.finditer(content):
        raw_url = html.unescape(anchor_match.group(3))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in amazon_hosts:
            continue
        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        query = str(params.get("k", "")).strip().casefold()
        if query:
            existing_amazon_queries.add(query)

    def replace(match: re.Match[str]) -> str:
        anchor = match.group(1)
        raw_url = html.unescape(match.group(3))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in ebay_hosts:
            return anchor

        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        query = str(params.get("_nkw", "")).strip()
        if not query or query.casefold() in existing_amazon_queries:
            return anchor

        amazon_url = f"{amazon_base}?{urlencode({'k': query})}"
        safe_url = html.escape(amazon_url, quote=True)
        amazon_anchor = (
            f'<a href="{safe_url}" rel="sponsored nofollow">{amazon_label}</a>'
        )
        existing_amazon_queries.add(query.casefold())
        return anchor + "\n" + amazon_anchor

    return FULL_ANCHOR_RE.sub(replace, content)


def add_amazon_tracking(content: str, market: str) -> str:
    """Ensure every Amazon link carries the correct market-specific Associates tag."""

    hosts = UK_AMAZON_HOSTS if market == "uk" else US_AMAZON_HOSTS
    tag = UK_AMAZON_TAG if market == "uk" else US_AMAZON_TAG

    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_url = html.unescape(match.group(2))
        parts = urlsplit(raw_url)
        host = parts.netloc.casefold().split(":", 1)[0]
        if host not in hosts:
            return match.group(0)

        existing = parse_qsl(parts.query, keep_blank_values=True)
        query = [(key, value) for key, value in existing if key.casefold() != "tag"]
        query.append(("tag", tag))
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
    """Prefer a wide AI editorial hero, falling back to the Pinterest artwork."""

    ai_path = ROOT / "assets" / "ai" / market / f"{slug}.jpg"
    ai_url = (
        "https://raw.githubusercontent.com/kevinamartin88/"
        f"worth-buying-uk/main/assets/ai/{market}/{slug}.jpg"
    )

    if market == "uk":
        fallback_path = ROOT / "assets" / "pinterest" / f"{slug}.png"
        fallback_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/{slug}.png"
        )
    else:
        fallback_path = ROOT / "assets" / "pinterest" / "us" / f"{slug}.png"
        fallback_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/us/{slug}.png"
        )

    if ai_path.exists():
        image_url = ai_url
        max_width = "900px"
    elif fallback_path.exists():
        image_url = fallback_url
        max_width = "460px"
    else:
        return ""

    alt = html.escape(title, quote=True)
    return (
        '<div class="wb-article-hero" style="margin:0 0 26px 0;text-align:center;">'
        f'<img src="{image_url}" alt="{alt}" loading="eager" '
        f'style="width:100%;max-width:{max_width};height:auto;display:block;'
        'margin:0 auto;border-radius:16px;box-shadow:0 10px 30px rgba(8,47,91,.14);" />'
        '</div>\n'
    )


def send_email(subject: str, html_content: str, to_address: str) -> None:
    """Send the HTML body directly, used only for Mail2Blogger mode."""

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


def send_ready_to_publish_email(
    *,
    market: str,
    slug: str,
    title: str,
    labels: list[str],
    category: str,
    html_content: str,
    to_address: str,
) -> None:
    """Email a human-ready Blogger package without posting to Blogger."""

    smtp_email = os.environ["SMTP_EMAIL"]
    smtp_password = os.environ["SMTP_APP_PASSWORD"]
    market_name = "Worth Buying UK" if market == "uk" else "Worth Buying USA"
    labels_text = ", ".join(str(label) for label in labels if str(label).strip()) or "None"

    instructions_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;line-height:1.5">
      <h2>READY TO PUBLISH - {html.escape(market_name)}</h2>
      <p>This article is prepared but has <strong>not</strong> been sent to Blogger automatically.</p>
      <ol>
        <li>Open Blogger and create a new post on <strong>{html.escape(market_name)}</strong>.</li>
        <li>Use the title below.</li>
        <li>Switch the Blogger editor to <strong>HTML view</strong>.</li>
        <li>Copy the HTML from the attached <strong>{html.escape(slug)}.html</strong> file and paste it into Blogger.</li>
        <li>Add the labels shown below, then publish normally.</li>
      </ol>
      <p><strong>Title:</strong> {html.escape(title)}</p>
      <p><strong>Primary category:</strong> {html.escape(category)}</p>
      <p><strong>Labels:</strong> {html.escape(labels_text)}</p>
      <p>After you publish it, the scheduled automation will detect the public Blogger URL and continue the existing X/Buffer and Pinterest-feed steps automatically.</p>
      <hr>
      <h3>Article preview</h3>
      {html_content}
    </div>
    """

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"[READY TO PUBLISH][{market.upper()}] {title}"
    msg["From"] = smtp_email
    msg["To"] = to_address

    body = MIMEMultipart("alternative")
    body.attach(
        MIMEText(
            (
                f"READY TO PUBLISH - {market_name}\n\n"
                f"Title: {title}\n"
                f"Primary category: {category}\n"
                f"Labels: {labels_text}\n\n"
                "Open Blogger, create a new post, switch to HTML view, paste the "
                f"contents of the attached {slug}.html file, add the labels, and publish.\n\n"
                "The automation will detect the published URL and continue the social steps."
            ),
            "plain",
            "utf-8",
        )
    )
    body.attach(MIMEText(instructions_html, "html", "utf-8"))
    msg.attach(body)

    attachment = MIMEText(html_content, "html", "utf-8")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"{slug}.html",
    )
    msg.attach(attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, [to_address], msg.as_string())


def title_tokens(value: str) -> list[str]:
    """Normalise a Blogger/article title for safe near-exact matching."""
    return re.findall(r"[a-z0-9]+", " ".join(str(value).casefold().split()))


def titles_match(wanted_title: str, entry_title: str) -> bool:
    """Allow small human title edits without matching unrelated articles.

    Exact normalised titles always match. Otherwise one title must contain all
    tokens from the other, with no more than four additional tokens. This
    safely handles edits such as adding "for Winter" while remaining strict
    enough to avoid broad keyword matching.
    """
    wanted_tokens = title_tokens(wanted_title)
    entry_tokens = title_tokens(entry_title)
    if not wanted_tokens or not entry_tokens:
        return False

    if wanted_tokens == entry_tokens:
        return True

    wanted_set = set(wanted_tokens)
    entry_set = set(entry_tokens)
    token_gap = abs(len(entry_tokens) - len(wanted_tokens))

    return token_gap <= 4 and (
        wanted_set.issubset(entry_set)
        or entry_set.issubset(wanted_set)
    )


def find_public_post_url(site_url: str, title: str) -> str | None:
    feed_url = f"{site_url.rstrip('/')}/feeds/posts/default?alt=json&max-results=50"
    req = Request(feed_url, headers={"User-Agent": "WorthBuyingPublisher/1.0"})
    with urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = payload.get("feed", {}).get("entry", [])
    for entry in entries:
        entry_title = " ".join(str(entry.get("title", {}).get("$t", "")).split())
        if not titles_match(title, entry_title):
            continue
        if entry_title != " ".join(title.split()):
            print(
                f"[title-match] Matched expected title '{title}' to Blogger title "
                f"'{entry_title}'."
            )
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
    attempts: int = 18,
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

    delivery_mode = os.getenv("BLOGGER_EMAIL_DELIVERY_MODE", "manual").strip().lower()
    if delivery_mode not in {"manual", "mail2blogger"}:
        raise ValueError("BLOGGER_EMAIL_DELIVERY_MODE must be 'manual' or 'mail2blogger'")

    if market == "uk":
        articles_dir = ROOT / "articles"
        blogger_email_env = "BLOGGER_UK_EMAIL_POST_ADDRESS"
        blog_state_path = ROOT / "state" / "articles_published.json"
    else:
        articles_dir = ROOT / "articles-us"
        blogger_email_env = "BLOGGER_US_EMAIL_POST_ADDRESS"
        blog_state_path = ROOT / "state" / "articles_us_published.json"

    if delivery_mode == "manual":
        target_email = (
            os.getenv("READY_TO_PUBLISH_EMAIL", "").strip()
            or os.environ["SMTP_EMAIL"].strip()
        )
    else:
        target_email = os.getenv(blogger_email_env, "").strip()
        if not target_email:
            raise RuntimeError(
                f"{blogger_email_env} is required when BLOGGER_EMAIL_DELIVERY_MODE=mail2blogger"
            )

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
        category = primary_category(article)
        state_key = f"{market}:{slug}"

        # Mail2Blogger is a create-only fallback. Never email an article that
        # already exists in the normal Blogger publication state, otherwise an
        # edit could accidentally create a duplicate public post.
        existing_blog = blog_state.get(slug)
        if existing_blog and existing_blog.get("status") == "published":
            print(f"[skip] {slug}: already exists on Blogger")
            continue

        emailed = email_state.get(state_key)

        # Before sending any manual READY TO PUBLISH email, check whether the
        # article is already live. This prevents a new workflow run (for
        # example after an unrelated code merge) from emailing a draft that has
        # already been published manually.
        if delivery_mode == "manual":
            existing_url = resolve_public_url(
                lookup_urls,
                public_site_url,
                title,
                attempts=1,
            )
            if existing_url:
                blog_state[slug] = {
                    "post_id": None,
                    "url": existing_url,
                    "title": title,
                    "status": "published",
                    "source_sha": source_sha,
                    "source_file": path.name,
                    "publisher": "manual",
                    "primary_category": category,
                }
                save_json(blog_state_path, blog_state)

                previous = emailed or {}
                email_state[state_key] = {
                    **previous,
                    "title": title,
                    "source_sha": source_sha,
                    "source_file": path.name,
                    "market": market,
                    "primary_category": category,
                    "sent": bool(previous.get("sent", False)),
                    "delivery_status": "published",
                    "delivery_mode": "manual",
                    "url": existing_url,
                }
                save_json(EMAIL_STATE_PATH, email_state)
                print(f"[published] {title}: {existing_url}")
                continue

        retrying = email_retry_due(emailed, delivery_mode)
        source_changed = bool(emailed) and emailed.get("source_sha") != source_sha

        # Manual packages are deliberately one-shot per market + slug. Once a
        # READY TO PUBLISH email has been sent for an article, later workflow
        # runs only check Blogger for the public URL; they never send the same
        # article again automatically, even if source metadata changes.
        needs_manual_package = delivery_mode == "manual" and not emailed
        needs_mail2blogger_send = (
            delivery_mode == "mail2blogger" and (not emailed or source_changed or retrying)
        )

        if needs_manual_package or needs_mail2blogger_send:
            content = (
                hero_image_html(slug, title, market)
                + category_marker_html(category, public_site_url)
                + style_retailer_buttons(
                    add_amazon_tracking(
                        add_epn_tracking(
                            add_amazon_search_alternatives(
                                article["content_html"],
                                market,
                            ),
                            market,
                        ),
                        market,
                    )
                )
            )
            if delivery_mode == "manual":
                send_ready_to_publish_email(
                    market=market,
                    slug=slug,
                    title=title,
                    labels=list(article.get("labels", [])),
                    category=category,
                    html_content=content,
                    to_address=target_email,
                )
                delivery_status = "awaiting_manual_publish"
                action = "ready-email-sent"
            else:
                send_email(
                    subject=title,
                    html_content=content,
                    to_address=target_email,
                )
                delivery_status = "awaiting_public_url"
                action = "resent" if retrying or source_changed else "sent"

            previous_attempts = int((emailed or {}).get("send_attempts", 0))
            email_state[state_key] = {
                "title": title,
                "source_sha": source_sha,
                "source_file": path.name,
                "market": market,
                "primary_category": category,
                "sent": True,
                "send_attempts": previous_attempts + 1,
                "last_sent_at": utc_now_iso(),
                "delivery_status": delivery_status,
                "delivery_mode": delivery_mode,
            }
            save_json(EMAIL_STATE_PATH, email_state)
            print(f"[{action}] {title}")
        else:
            print(
                f"[resolve] {slug}: publication package already sent; "
                "checking public Blogger feed"
            )

        url = resolve_public_url(
            lookup_urls,
            public_site_url,
            title,
            attempts=1 if delivery_mode == "manual" else 18,
        )
        if not url:
            if delivery_mode == "manual":
                print(
                    f"[waiting] '{title}' has not appeared on the public Blogger feed yet. "
                    "Publish it manually from the READY TO PUBLISH email; a scheduled "
                    "reconciliation run will pick it up afterwards."
                )
            else:
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
            "publisher": "manual" if delivery_mode == "manual" else "email",
            "primary_category": category,
        }
        save_json(blog_state_path, blog_state)
        email_state[state_key]["url"] = url
        email_state[state_key]["delivery_status"] = "published"
        save_json(EMAIL_STATE_PATH, email_state)
        print(f"[published] {title}: {url}")


if __name__ == "__main__":
    main()
