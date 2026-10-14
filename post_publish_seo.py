"""Check newly published Blogger URLs and optionally submit their sitemap to GSC.

This is deliberately advisory: a slow sitemap or Search Console must not undo a
successful Blogger publication or prevent the existing social steps from running.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.search_console import TOKEN_URI, build_service, choose_site, configured
from src.site_config import get_site_config, get_site_host, get_site_url
from src.google_discovery_report import inspection_record, new_report, save_report, write_summary


ROOT = Path(__file__).resolve().parent
STATE_FILES = {"uk": "state/articles_published.json", "us": "state/articles_us_published.json"}
WRITE_SCOPE = "https://www.googleapis.com/auth/webmasters"


class PageSignals(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.descriptions: list[str] = []
        self.links: list[str] = []
        self._in_head = False
        self.canonical: str | None = None
        self.json_ld: list[str] = []
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "head":
            self._in_head = True
        if tag == "meta" and self._in_head and (attributes.get("name") or "").lower() == "description":
            self.descriptions.append(attributes.get("content") or "")
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag == "link" and "canonical" in (attributes.get("rel") or "").lower().split():
            self.canonical = attributes.get("href")
        if tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self.json_ld.append("")

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self.json_ld[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._in_head = False
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
    keys = ("url", "status", "source_sha", "publish_fingerprint", "seo_revision")
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


def sitemap_contains(session: requests.Session, sitemap: str, target: str, host: str, depth: int = 0, cache: dict | None = None) -> bool:
    if depth > 2 or not same_site(sitemap, host):
        return False
    cache = cache if cache is not None else {}
    if sitemap not in cache:
        response = session.get(sitemap, timeout=15)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        cache[sitemap] = (root.tag, [node.text.strip() for node in root.iter()
                                   if node.tag.rsplit("}", 1)[-1] == "loc" and node.text])
    root_tag, locations = cache[sitemap]
    if target in locations:
        return True
    if root_tag.endswith("sitemapindex"):
        for location in locations[:30]:
            if same_site(location, host) and sitemap_contains(session, location, target, host, depth + 1, cache):
                return True
    return False


def inspect_page(session: requests.Session, url: str, host: str) -> dict | None:
    if not same_site(url, host):
        print(f"[seo-warning] URL is outside the active site: {url}")
        return {"outside_site": True}
    response = session.get(url, timeout=15)
    response.raise_for_status()
    if not same_site(response.url, host):
        print(f"[seo-warning] Page redirects outside the active site: {url}")
        return {"http_status": response.status_code, "outside_site": True}
    signals = PageSignals()
    signals.feed(response.text)
    print(f"[seo] Page reachable ({response.status_code}): {url}")
    if signals.canonical:
        print(f"[seo] Canonical: {signals.canonical}")
        if signals.canonical.rstrip("/") != response.url.rstrip("/"):
            print("[seo-warning] Canonical differs from the published URL")
    else:
        print("[seo-warning] No canonical link found in the rendered page")
    if len(signals.descriptions) != 1 or not signals.descriptions[0].strip():
        print("[seo-warning] Expected one nonempty description in the server-rendered head")
    else:
        print(f"[seo] Server-rendered description: {signals.descriptions[0]}")
    if 'class="wb-published-seo"' in response.text:
        print("[seo] Generated-description bridge present; browser verification still required")
    if "wb_retailer_click" in response.text:
        print("[seo] Retailer measurement listener present; GA4 receipt requires browser verification")
    valid = 0
    for block in signals.json_ld:
        try:
            json.loads(block)
            valid += 1
        except json.JSONDecodeError:
            print("[seo-warning] Invalid JSON-LD block in rendered page")
    print(f"[seo] Valid JSON-LD blocks: {valid}")
    return {"http_status": response.status_code, "canonical": signals.canonical,
            "head_description_present": bool(signals.descriptions),
            "generated_description_bridge": "wb-published-seo" in response.text,
            "retailer_tracking_present": "wb_retailer_click" in response.text}


def search_console(market: str, urls: list[str], sitemaps: list[str], checkpoint=None) -> dict:
    result = {"property": None, "sitemaps": [{"url": url, "state": "pending"} for url in sitemaps],
              "inspections": {url: {"state": "unconfirmed"} for url in urls}}

    def persist():
        if checkpoint:
            checkpoint(result)

    persist()
    # Submit discovery hints before slower inspection/public-page checks. Each
    # feed has its own outcome, so one failure cannot hide the other result.
    if not os.getenv("GSC_WRITE_REFRESH_TOKEN"):
        for row in result["sitemaps"]:
            row.update(state="unavailable", reason="MissingWriteCredentials")
        print("[seo-warning] Sitemap submission unavailable: write credentials absent")
        persist()
    else:
        try:
            credentials = Credentials(
                token=None, refresh_token=os.environ["GSC_WRITE_REFRESH_TOKEN"], token_uri=TOKEN_URI,
                client_id=os.getenv("GSC_WRITE_CLIENT_ID") or os.environ["GSC_CLIENT_ID"],
                client_secret=os.getenv("GSC_WRITE_CLIENT_SECRET") or os.environ["GSC_CLIENT_SECRET"],
                scopes=[WRITE_SCOPE],
            )
            writer = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
            site = choose_site(writer, market)
            if not site:
                raise ValueError("NoMatchingSearchConsoleProperty")
            result["property"] = site
            for row in result["sitemaps"]:
                try:
                    writer.sitemaps().submit(siteUrl=site, feedpath=row["url"]).execute(num_retries=2)
                    row["state"] = "submitted"
                    print(f"[seo] Submitted {row['url']} to Search Console property {site}")
                except Exception as exc:
                    row.update(state="failed", reason=type(exc).__name__)
                    print(f"[seo-warning] Sitemap submission failed for {row['url']}: {type(exc).__name__}")
                persist()
        except Exception as exc:
            for row in result["sitemaps"]:
                if row["state"] == "pending":
                    row.update(state="failed", reason=type(exc).__name__)
            print(f"[seo-warning] Search Console writer unavailable: {type(exc).__name__}")
            persist()

    # Stored index inspection is read-only: this is not a request to index and
    # not a live Googlebot fetch test.
    if configured():
        try:
            service = build_service()
            site = choose_site(service, market)
            if not site:
                raise ValueError("NoMatchingSearchConsoleProperty")
            result["inspection_property"] = site
            result["property"] = result["property"] or site
            for url in urls:
                try:
                    response = service.urlInspection().index().inspect(
                        body={"inspectionUrl": url, "siteUrl": site}
                    ).execute(num_retries=2)
                    status = response.get("inspectionResult", {}).get("indexStatusResult", {})
                    result["inspections"][url] = inspection_record(status)
                    print(f"[seo] GSC {url}: {status.get('coverageState', 'status unavailable')}; "
                          f"last crawl: {status.get('lastCrawlTime', 'not reported')}")
                except Exception as exc:
                    result["inspections"][url] = {"state": "unconfirmed", "reason": type(exc).__name__}
                    print(f"[seo-warning] GSC inspection unconfirmed for {url}: {type(exc).__name__}")
                persist()
        except Exception as exc:
            for row in result["inspections"].values():
                if row["state"] == "unconfirmed":
                    row["reason"] = type(exc).__name__
            print(f"[seo-warning] Search Console read unavailable: {type(exc).__name__}")
            persist()
    else:
        for row in result["inspections"].values():
            row["reason"] = "MissingReadCredentials"
        print("[seo-warning] Index inspection unavailable: read credentials absent")
        persist()
    return result


def manual_indexing_summary(market: str, urls: list[str]) -> None:
    """List changed URLs in Actions; this does not submit indexing requests."""
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if not target:
        return
    allowed = list(dict.fromkeys(url for url in urls if same_site(url, get_site_host(market))))
    if not allowed:
        return
    links = "\n".join(
        f'<li><a href="{html.escape(url, quote=True)}">{html.escape(url)}</a></li>' for url in allowed
    )
    summary = (
        f"\n## {market.upper()} indexing review: new or changed guides\n\n"
        "Sitemap submission and individual indexing requests are separate actions. "
        "The workflow has not requested indexing for these URLs.\n\n"
        "For an important new or substantially improved guide, inspect its public URL in "
        "Search Console, check the live test, then request indexing once. "
        "Repeated submissions do not improve queue priority.\n\n"
        f"<ul>\n{links}\n</ul>\n"
        "[Google’s recrawl guidance](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)\n"
    )
    try:
        with Path(target).open("a", encoding="utf-8") as handle:
            handle.write(summary)
        print(f"[seo] Added {len(allowed)} changed URL(s) to the manual indexing review summary")
    except OSError as exc:
        print(f"[seo-warning] Could not write indexing review summary: {type(exc).__name__}: {exc}")


def recent_posts(market: str, limit: int = 10) -> list[dict]:
    state = json.loads((ROOT / STATE_FILES[market]).read_text(encoding="utf-8"))
    rows = [row for row in state.values() if row.get("status") == "published" and row.get("url")]
    def featured_date(row):
        candidate = str(row.get("daily_featured_date") or str(row.get("source_sha") or "")[:10])
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return ""
    rows.sort(key=lambda row: (featured_date(row), str(row.get("url") or "")), reverse=True)
    selected = []
    seen = set()
    for row in rows:
        url = public_url(str(row["url"]), market)
        if url and url not in seen:
            selected.append(row)
            seen.add(url)
        if len(selected) >= limit:
            break
    return selected


def run(market: str, recent_limit: int | None = None, report_path: Path | None = None) -> dict:
    mode = "daily-follow-up" if recent_limit is not None else "after-publication"
    posts = recent_posts(market, recent_limit) if recent_limit is not None else changed_posts(market)
    urls = list(dict.fromkeys(url for post in posts
                if (url := public_url(str(post["url"]), market))))
    report = new_report(market, urls, mode)
    report_path = report_path or ROOT / "reports" / f"google-discovery-{market}.json"
    save_report(report_path, report)
    if not urls:
        report.update(complete=True, outcome="no_changed_or_selected_urls")
        save_report(report_path, report)
        print(f"[seo] {market.upper()}: no URLs requiring this discovery check")
        return report
    host = get_site_host(market)
    sitemap = urljoin(get_site_url(market), "sitemap.xml")
    pages_sitemap = urljoin(get_site_url(market), "sitemap-pages.xml")

    def checkpoint(google):
        report["google"] = google
        save_report(report_path, report)

    search_console(market, urls, [sitemap, pages_sitemap], checkpoint=checkpoint)
    # Only new/changed publication runs fetch public pages. The scheduled
    # follow-up uses Google's stored inspection status and checks the sitemap.
    with requests.Session() as session:
        cache = {}
        try:
            sitemap_contains(session, sitemap, urls[0], host, cache=cache)
        except (requests.RequestException, ElementTree.ParseError) as exc:
            report["sitemap_check_error"] = type(exc).__name__
        for url in urls:
            public = {}
            if "sitemap_check_error" not in report:
                try:
                    public["sitemap_contains_url"] = sitemap_contains(session, sitemap, url, host, cache=cache)
                except (requests.RequestException, ElementTree.ParseError) as exc:
                    public["sitemap_error"] = type(exc).__name__
            if recent_limit is None:
                try:
                    public.update(inspect_page(session, url, host) or {})
                except requests.RequestException as exc:
                    public["page_check_error"] = type(exc).__name__
                    if exc.response is not None:
                        public["http_status"] = exc.response.status_code
            report["public_checks"][url] = public
            save_report(report_path, report)
    report["complete"] = True
    report["attention_required"] = (
        any(row["state"] != "submitted" for row in report["google"]["sitemaps"])
        or any(row["state"] != "indexed" for row in report["google"]["inspections"].values())
        or any(row.get("sitemap_contains_url") is not True for row in report["public_checks"].values())
        or any(row.get("page_check_error") or row.get("outside_site") for row in report["public_checks"].values())
    )
    save_report(report_path, report)
    write_summary(report)
    print(f"[seo] Discovery report saved: {report_path}; attention required: {report['attention_required']}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument("--recent", type=int, choices=range(1, 51), help="Recheck up to 50 recent published guides")
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()
    run(args.market, args.recent, args.report_path)
