"""Check newly published Blogger URLs and optionally submit their sitemap to GSC.

This is deliberately advisory: a slow sitemap or Search Console must not undo a
successful Blogger publication or prevent the existing social steps from running.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.search_console import TOKEN_URI, build_service, choose_site, configured
from src.site_config import get_site_config, get_site_host, get_site_url


ROOT = Path(__file__).resolve().parent
STATE_FILES = {"uk": "state/articles_published.json", "us": "state/articles_us_published.json"}
WRITE_SCOPE = "https://www.googleapis.com/auth/webmasters"


class PageSignals(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical: str | None = None
        self.json_ld: list[str] = []
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "link" and "canonical" in (attributes.get("rel") or "").lower().split():
            self.canonical = attributes.get("href")
        if tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self.json_ld.append("")

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self.json_ld[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_json_ld = False


def changed_posts(market: str) -> list[dict]:
    path = STATE_FILES[market]
    current = json.loads((ROOT / path).read_text(encoding="utf-8"))
    try:
        previous_text = subprocess.check_output(
            ["git", "show", f"HEAD:{path}"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        )
        previous = json.loads(previous_text)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        previous = {}
    keys = ("url", "status", "source_sha", "publish_fingerprint")
    return [
        post for slug, post in current.items()
        if post.get("status") == "published" and post.get("url")
        and any(post.get(key) != previous.get(slug, {}).get(key) for key in keys)
    ]


def same_site(url: str, host: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname == host


def public_url(url: str, market: str) -> str | None:
    """Map Blogger's Blogspot API URL to the active public custom domain."""
    parts = urlsplit(url)
    active_host = get_site_host(market)
    backend_host = urlsplit(get_site_config(market)["blogspot_url"]).hostname
    if parts.scheme != "https" or parts.hostname not in {active_host, backend_host}:
        return None
    return urlunsplit(("https", active_host, parts.path, parts.query, parts.fragment))


def sitemap_contains(session: requests.Session, sitemap: str, target: str, host: str, depth: int = 0) -> bool:
    if depth > 2 or not same_site(sitemap, host):
        return False
    response = session.get(sitemap, timeout=15)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    locations = [
        node.text.strip() for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "loc" and node.text
    ]
    if target in locations:
        return True
    if root.tag.endswith("sitemapindex"):
        for location in locations[:30]:
            if same_site(location, host) and sitemap_contains(session, location, target, host, depth + 1):
                return True
    return False


def inspect_page(session: requests.Session, url: str, host: str) -> None:
    if not same_site(url, host):
        print(f"[seo-warning] URL is outside the active site: {url}")
        return
    response = session.get(url, timeout=15)
    response.raise_for_status()
    if not same_site(response.url, host):
        print(f"[seo-warning] Page redirects outside the active site: {url}")
        return
    signals = PageSignals()
    signals.feed(response.text)
    print(f"[seo] Page reachable ({response.status_code}): {url}")
    if signals.canonical:
        print(f"[seo] Canonical: {signals.canonical}")
        if signals.canonical.rstrip("/") != response.url.rstrip("/"):
            print("[seo-warning] Canonical differs from the published URL")
    else:
        print("[seo-warning] No canonical link found in the rendered page")
    valid = 0
    for block in signals.json_ld:
        try:
            json.loads(block)
            valid += 1
        except json.JSONDecodeError:
            print("[seo-warning] Invalid JSON-LD block in rendered page")
    print(f"[seo] Valid JSON-LD blocks: {valid}")


def search_console(market: str, urls: list[str], sitemap: str) -> None:
    site = None
    if configured():
        try:
            service = build_service()
            site = choose_site(service, market)
            if site:
                for url in urls:
                    try:
                        result = service.urlInspection().index().inspect(
                            body={"inspectionUrl": url, "siteUrl": site}
                        ).execute()
                        status = result.get("inspectionResult", {}).get("indexStatusResult", {})
                        print(f"[seo] GSC {url}: {status.get('coverageState', 'status unavailable')}; "
                              f"last crawl: {status.get('lastCrawlTime', 'not reported')}")
                    except Exception as exc:
                        print(f"[seo-warning] GSC URL inspection failed for {url}: {type(exc).__name__}: {exc}")
        except Exception as exc:
            print(f"[seo-warning] Search Console read failed: {type(exc).__name__}: {exc}")
    else:
        print("[seo] Search Console read-only credentials absent; index inspection skipped")

    if not os.getenv("GSC_WRITE_REFRESH_TOKEN"):
        print("[seo] GSC_WRITE_REFRESH_TOKEN absent; sitemap submission skipped")
        return
    try:
        credentials = Credentials(
            token=None,
            refresh_token=os.environ["GSC_WRITE_REFRESH_TOKEN"],
            token_uri=TOKEN_URI,
            client_id=os.environ["GSC_CLIENT_ID"],
            client_secret=os.environ["GSC_CLIENT_SECRET"],
            scopes=[WRITE_SCOPE],
        )
        writer = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        site = site or choose_site(writer, market)
        if not site:
            print("[seo-warning] No matching Search Console property for sitemap submission")
            return
        writer.sitemaps().submit(siteUrl=site, feedpath=sitemap).execute()
        print(f"[seo] Submitted {sitemap} to Search Console property {site}")
    except Exception as exc:
        print(f"[seo-warning] Sitemap submission failed: {type(exc).__name__}: {exc}")


def run(market: str) -> None:
    posts = changed_posts(market)
    if not posts:
        print(f"[seo] {market.upper()}: no newly published or changed URLs")
        return
    host = get_site_host(market)
    sitemap = urljoin(get_site_url(market), "sitemap.xml")
    with requests.Session() as session:
        urls = []
        for post in posts:
            url = public_url(str(post["url"]), market)
            if not url:
                print(f"[seo-warning] Published URL is outside the {market.upper()} site: {post['url']}")
                continue
            urls.append(url)
            try:
                inspect_page(session, url, host)
                print(f"[seo] Sitemap contains URL: {sitemap_contains(session, sitemap, url, host)} ({url})")
            except (requests.RequestException, ElementTree.ParseError) as exc:
                print(f"[seo-warning] Public discovery check failed for {url}: {type(exc).__name__}: {exc}")
        if urls:
            search_console(market, urls, sitemap)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    run(parser.parse_args().market)
