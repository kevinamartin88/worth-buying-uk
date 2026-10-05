from __future__ import annotations

import json
import math
import time
from typing import Iterable

import requests

from src.shopping_cache import cached_topics, cooling_down, remember


EXPLORE_URL = "https://trends.google.com/trends/api/explore"
MULTILINE_URL = "https://trends.google.com/trends/api/widgetdata/multiline"
USER_AGENT = (
    "Mozilla/5.0 (compatible; WorthBuyingShoppingResearch/1.0; "
    "+https://www.worthbuyinguk.co.uk/)"
)
ANCHOR_TERM = "air fryer"
TIMEFRAME = "today 3-m"
BATCH_SIZE = 4
REQUEST_TIMEOUT = 15


def _strip_prefix(text: str) -> str:
    value = text.lstrip()
    if value.startswith(")]}'"):
        newline = value.find("\n")
        return value[newline + 1 :] if newline >= 0 else value[4:]
    return value


def _json_response(response: requests.Response) -> dict:
    response.raise_for_status()
    return json.loads(_strip_prefix(response.text))


def _explore_widgets(
    session: requests.Session,
    terms: list[str],
    geo: str,
    hl: str,
) -> list[dict]:
    request_payload = {
        "comparisonItem": [
            {"keyword": term, "geo": geo, "time": TIMEFRAME}
            for term in terms
        ],
        "category": 0,
        # Google Trends uses "froogle" for Google Shopping search interest.
        "property": "froogle",
    }
    response = session.get(
        EXPLORE_URL,
        params={
            "hl": hl,
            "tz": "0",
            "req": json.dumps(request_payload, separators=(",", ":")),
        },
        timeout=REQUEST_TIMEOUT,
    )
    payload = _json_response(response)
    return list(payload.get("widgets") or [])


def _timeline(
    session: requests.Session,
    widget: dict,
    hl: str,
) -> list[dict]:
    response = session.get(
        MULTILINE_URL,
        params={
            "hl": hl,
            "tz": "0",
            "req": json.dumps(widget["request"], separators=(",", ":")),
            "token": widget["token"],
        },
        timeout=REQUEST_TIMEOUT,
    )
    payload = _json_response(response)
    return list((payload.get("default") or {}).get("timelineData") or [])


def _averages(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    recent = values[-14:] if len(values) >= 14 else values
    prior_source = values[:-14]
    prior = prior_source[-28:] if prior_source else []
    recent_avg = sum(recent) / max(len(recent), 1)
    prior_avg = sum(prior) / max(len(prior), 1) if prior else recent_avg
    return recent_avg, prior_avg


def _score(
    candidate_values: list[float],
    anchor_values: list[float],
) -> dict:
    current, prior = _averages(candidate_values)
    anchor_current, _ = _averages(anchor_values)

    if current <= 0:
        return {
            "score": 0.0,
            "shopping_current": 0.0,
            "shopping_prior": round(prior, 2),
            "shopping_momentum": 0.0,
            "shopping_relative_to_anchor": 0.0,
        }

    momentum = current / max(prior, 1.0)
    relative = current / max(anchor_current, 1.0)

    # Search interest is normalised by Google within each comparison request.
    # Because the same air-fryer anchor appears in every batch, relative-to-
    # anchor makes the batches broadly comparable. Momentum rewards products
    # that are rising now rather than merely being evergreen.
    popularity_score = min(70.0, 35.0 * math.sqrt(max(relative, 0.0)))
    momentum_score = min(30.0, 20.0 * max(momentum - 0.75, 0.0))
    score = round(min(100.0, popularity_score + momentum_score), 2)

    return {
        "score": score,
        "shopping_current": round(current, 2),
        "shopping_prior": round(prior, 2),
        "shopping_momentum": round(momentum, 3),
        "shopping_relative_to_anchor": round(relative, 3),
    }


def _chunks(items: list[tuple], size: int) -> Iterable[list[tuple]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def rank_topics_by_google_shopping(
    topics: list[tuple],
    market: str,
) -> list[tuple[tuple, dict]]:
    """Rank product topics using external Google Shopping search interest.

    This does not use Search Console or any WorthBuying traffic. It compares
    public Google Trends Shopping-search interest in GB/US over the last
    three months, with a shared anchor term in every batch.
    """
    if not topics:
        return []

    cached = cached_topics(topics, market)
    if len(cached) == len(topics):
        print(f"[shopping-cache] {market.upper()}: using observations less than 24 hours old")
        return cached
    if cooling_down(market):
        print(f"[shopping-cooldown] {market.upper()}: respecting Google's rate limit")
        return cached

    geo = "GB" if market.casefold() == "uk" else "US"
    hl = "en-GB" if geo == "GB" else "en-US"
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": f"https://trends.google.com/trends/explore?geo={geo}",
        }
    )

    ranked: list[tuple[tuple, dict]] = []
    try:
        for batch in _chunks(topics, BATCH_SIZE):
            batch_terms = [str(topic[2]).strip() for topic in batch]
            terms = [ANCHOR_TERM]
            for term in batch_terms:
                if term.casefold() != ANCHOR_TERM.casefold():
                    terms.append(term)

            widgets = _explore_widgets(session, terms, geo, hl)
            widget = next(
                (item for item in widgets if item.get("id") == "TIMESERIES"),
                None,
            )
            if not widget:
                continue

            timeline = _timeline(session, widget, hl)
            series: list[list[float]] = [[] for _ in terms]
            for point in timeline:
                values = point.get("value") or []
                for index in range(min(len(values), len(series))):
                    try:
                        series[index].append(float(values[index]))
                    except (TypeError, ValueError):
                        series[index].append(0.0)

            anchor_values = series[0] if series else []
            term_to_values = {
                term.casefold(): series[index]
                for index, term in enumerate(terms)
                if index < len(series)
            }

            for topic in batch:
                query = str(topic[2]).strip()
                values = term_to_values.get(query.casefold())
                if values is None and query.casefold() == ANCHOR_TERM.casefold():
                    values = anchor_values
                if not values:
                    continue

                signal = {
                    "query": query,
                    "source": "google-trends-google-shopping",
                    "geo": geo,
                    "timeframe": TIMEFRAME,
                    "search_type": "Google Shopping",
                    **_score(values, anchor_values),
                }
                if float(signal["score"]) > 0:
                    ranked.append((topic, signal))

            # Be polite to the public Trends endpoint and reduce 429 risk.
            time.sleep(1.0)

    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        remember(market, ranked, rate_limited=status == 429)
        print(
            f"[shopping-trends-warning] {market.upper()}: lookup unavailable "
            f"({type(exc).__name__}, HTTP {status}); retaining only recent observed signals."
        )
        return cached_topics(topics, market)
    finally:
        session.close()

    remember(market, ranked)
    ranked.sort(
        key=lambda pair: (
            -float(pair[1].get("score") or 0),
            -float(pair[1].get("shopping_current") or 0),
            str(pair[0][0]),
        )
    )
    return ranked

