from __future__ import annotations

import math
import os
import re
from datetime import date, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"

TARGETS = {
    "uk": ("worthbuyinguk.co.uk", "worthbuyinguk.blogspot.com"),
    "us": ("worthbuyingusa.com", "worthbuyingusa.blogspot.com"),
}

GENERIC_TOKENS = {
    "best", "buy", "buying", "guide", "guides", "worth", "current", "new",
    "home", "kitchen", "smart", "portable", "electric", "wireless",
    "computer", "car", "gaming", "the", "and", "for", "with", "from",
    "uk", "usa", "2026",
}

WEAK_SINGLE_TOKENS = {
    "apple", "home", "smart", "portable", "electric", "wireless",
    "computer", "car", "gaming",
}


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in normalise(value).split()
        if len(token) >= 3 and token not in GENERIC_TOKENS
    }


def configured() -> bool:
    return all(
        os.getenv(name)
        for name in ("GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN")
    )


def build_service():
    if not configured():
        return None

    credentials = Credentials(
        token=None,
        refresh_token=os.environ["GSC_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["GSC_CLIENT_ID"],
        client_secret=os.environ["GSC_CLIENT_SECRET"],
        scopes=[SEARCH_CONSOLE_SCOPE],
    )
    return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)


def site_override(market: str) -> str:
    key = "GSC_UK_SITE_URL" if market.casefold() == "uk" else "GSC_US_SITE_URL"
    return str(os.getenv(key, "")).strip()


def choose_site(service, market: str) -> str | None:
    override = site_override(market)
    if override:
        return override

    try:
        entries = service.sites().list().execute().get("siteEntry", [])
    except Exception as exc:
        print(
            f"[gsc-warning] {market.upper()}: could not list Search Console properties "
            f"({type(exc).__name__}: {exc})"
        )
        return None

    verified = [
        entry for entry in entries
        if entry.get("permissionLevel") != "siteUnverifiedUser"
    ]
    targets = TARGETS[market.casefold()]

    # Prefer a domain property for the custom domain, then a URL-prefix property,
    # then the Blogger fallback property.
    for target in targets:
        exact_domain = f"sc-domain:{target}"
        for entry in verified:
            if str(entry.get("siteUrl", "")).casefold() == exact_domain:
                return str(entry["siteUrl"])

        for entry in verified:
            site_url = str(entry.get("siteUrl", ""))
            if target in site_url.casefold():
                return site_url

    print(
        f"[gsc-warning] {market.upper()}: no matching verified Search Console property "
        f"was found for {', '.join(targets)}"
    )
    return None


def fetch_query_rows(
    market: str,
    lookback_days: int = 28,
    lag_days: int = 3,
    row_limit: int = 1000,
) -> tuple[str | None, list[dict]]:
    if not configured():
        print(
            f"[gsc-skip] {market.upper()}: GSC_CLIENT_ID/GSC_CLIENT_SECRET/"
            "GSC_REFRESH_TOKEN are not configured."
        )
        return None, []

    try:
        service = build_service()
        site_url = choose_site(service, market) if service is not None else None
        if not site_url:
            return None, []

        end = date.today() - timedelta(days=lag_days)
        start = end - timedelta(days=max(lookback_days - 1, 0))
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "type": "web",
            "rowLimit": max(1, min(int(row_limit), 25000)),
        }
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
    except Exception as exc:
        print(
            f"[gsc-warning] {market.upper()}: Search Console query failed "
            f"({type(exc).__name__}: {exc}); continuing without GSC."
        )
        return None, []

    rows: list[dict] = []
    for row in response.get("rows", []):
        keys = row.get("keys") or []
        query = " ".join(str(keys[0] if keys else "").split()).strip()
        if not query:
            continue
        rows.append(
            {
                "query": query,
                "clicks": float(row.get("clicks") or 0),
                "impressions": float(row.get("impressions") or 0),
                "ctr": float(row.get("ctr") or 0),
                "position": float(row.get("position") or 0),
                "source": "google-search-console",
                "site_url": site_url,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
        )

    return site_url, rows


def _topic_tokens(topic: tuple) -> set[str]:
    key, display, query = topic[0], topic[1], topic[2]
    return tokens(f"{key.replace('-', ' ')} {display} {query}")


def score_topic_query(topic: tuple, row: dict) -> float:
    query = str(row.get("query", ""))
    query_norm = normalise(query)
    query_tokens = tokens(query)
    topic_tokens = _topic_tokens(topic)

    overlap = query_tokens & topic_tokens
    if not overlap:
        return 0.0

    topic_query_norm = normalise(topic[2])
    key_norm = normalise(str(topic[0]).replace("-", " "))
    exact_query = bool(topic_query_norm and topic_query_norm in query_norm)
    exact_key = bool(key_norm and key_norm in query_norm)

    if len(overlap) == 1 and not exact_query and not exact_key:
        only = next(iter(overlap))
        if only in WEAK_SINGLE_TOKENS:
            return 0.0

    impressions = max(float(row.get("impressions") or 0), 0.0)
    clicks = max(float(row.get("clicks") or 0), 0.0)
    ctr = max(min(float(row.get("ctr") or 0), 1.0), 0.0)
    position = max(float(row.get("position") or 0), 0.0)

    # Very small samples are too noisy to steer a daily article.
    if impressions < 5:
        return 0.0

    relevance = min(45.0, len(overlap) * 15.0)
    if exact_query:
        relevance += 20.0
    elif exact_key:
        relevance += 12.0

    impression_score = min(22.0, math.log10(impressions + 1.0) * 8.0)

    # Queries already ranking around positions 4-30 are often the most useful
    # content-opportunity signals: visible enough to prove demand, but with room
    # for a more targeted article or stronger title.
    if 4 <= position <= 10:
        position_score = 18.0
    elif 10 < position <= 20:
        position_score = 16.0
    elif 20 < position <= 30:
        position_score = 12.0
    elif 1 <= position < 4:
        position_score = 8.0
    elif 30 < position <= 50:
        position_score = 6.0
    else:
        position_score = 2.0

    # Reward proven impressions where CTR still leaves room to improve.
    ctr_score = max(0.0, min(12.0, (0.12 - ctr) * 100.0))
    click_score = min(8.0, math.log10(clicks + 1.0) * 5.0)

    return round(min(100.0, relevance + impression_score + position_score + ctr_score + click_score), 2)


def rank_topics_by_search_console(
    topics: list[tuple],
    market: str,
) -> list[tuple[tuple, dict]]:
    site_url, rows = fetch_query_rows(market)
    if not rows:
        return []

    ranked: list[tuple[tuple, dict]] = []
    for topic in topics:
        best_signal: dict | None = None
        best_score = 0.0

        for row in rows:
            score = score_topic_query(topic, row)
            if score > best_score:
                best_score = score
                best_signal = {**row, "score": score}

        if best_signal is not None and best_score > 0:
            best_signal["site_url"] = site_url
            ranked.append((topic, best_signal))

    ranked.sort(
        key=lambda pair: (
            -float(pair[1].get("score") or 0),
            -float(pair[1].get("impressions") or 0),
            str(pair[0][0]),
        )
    )
    return ranked
