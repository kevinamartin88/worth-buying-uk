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

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "email_published.json"

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


def main() -> None:
    market = os.getenv("MARKET", "uk").strip().lower()
    if market not in {"uk", "us"}:
        raise ValueError("MARKET must be 'uk' or 'us'")

    if market == "uk":
        articles_dir = ROOT / "articles"
        target_email = os.environ["BLOGGER_UK_EMAIL_POST_ADDRESS"]
    else:
        articles_dir = ROOT / "articles-us"
        target_email = os.environ["BLOGGER_US_EMAIL_POST_ADDRESS"]

    if not articles_dir.exists():
        print(f"No article directory found: {articles_dir}")
        return

    state = load_state()

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

        existing = state.get(state_key)
        if existing and existing.get("source_sha") == source_sha:
            print(f"[skip] {slug}: already emailed")
            continue

        content = add_epn_tracking(article["content_html"], market)

        send_email(
            subject=title,
            html_content=content,
            to_address=target_email,
        )

        state[state_key] = {
            "title": title,
            "source_sha": source_sha,
            "source_file": path.name,
            "market": market,
        }
        save_state(state)

        print(f"[sent] {title}")
        time.sleep(5)


if __name__ == "__main__":
    main()
