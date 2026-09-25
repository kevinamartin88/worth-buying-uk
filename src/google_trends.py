from __future__ import annotations

import math
import re
import urllib.request
import xml.etree.ElementTree as ET


RSS_URL = "https://trends.google.com/trending/rss?geo={geo}"
USER_AGENT = (
    "Mozilla/5.0 (compatible; WorthBuyingTrendResearch/1.0; "
    "+https://www.worthbuyinguk.co.uk/)"
)

GENERIC_TOPIC_TOKENS = {
    "best",
    "buy",
    "buying",
    "guide",
    "guides",
    "worth",
    "current",
    "new",
    "home",
    "kitchen",
    "smart",
    "portable",
    "electric",
    "wireless",
    "computer",
    "car",
    "gaming",
    "the",
    "and",
    "for",
    "with",
}

WEAK_SINGLE_TOKENS = {
    "apple",
    "home",
    "smart",
    "portable",
    "electric",
    "wireless",
    "computer",
    "car",
    "gaming",
}

BLOCKED_TITLE_TOKENS = {
    "vs",
    "score",
    "scores",
    "live",
    "results",
    "result",
    "weather",
    "news",
    "recall",
    "recalled",
    "warning",
    "lawsuit",
    "injury",
    "death",
    "dies",
    "deal",
    "deals",
    "sale",
    "coupon",
    "cheap",
}

PRETTY_WORDS = {
    "airpods": "AirPods",
    "iphone": "iPhone",
    "ipad": "iPad",
    "wifi": "Wi-Fi",
    "wi-fi": "Wi-Fi",
    "usb": "USB",
    "usb-c": "USB-C",
    "tv": "TV",
    "tvs": "TVs",
    "ssd": "SSD",
    "ssds": "SSDs",
    "pc": "PC",
    "pcs": "PCs",
}


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in normalise(value).split()
        if len(token) >= 3 and token not in GENERIC_TOPIC_TOKENS
    }


def parse_traffic(value: str | None) -> int:
    raw = str(value or "").strip().upper().replace(",", "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)", raw)
    if not match:
        return 0

    number = float(match.group(1))
    suffix = match.group(2)
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(number * multiplier)


def fetch_trending_searches(market: str, timeout: int = 8) -> list[dict]:
    geo = "GB" if market.casefold() == "uk" else "US"
    request = urllib.request.Request(
        RSS_URL.format(geo=geo),
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
        root = ET.fromstring(payload)
    except Exception as exc:
        print(
            f"[trends-warning] {market.upper()}: Google Trends RSS unavailable "
            f"({type(exc).__name__}: {exc}); using normal topic rotation."
        )
        return []

    rows: list[dict] = []
    for item in root.findall("./channel/item"):
        title = " ".join((item.findtext("title") or "").split()).strip()
        if not title:
            continue
        traffic_raw = item.findtext("{*}approx_traffic") or ""
        rows.append(
            {
                "query": title,
                "traffic": parse_traffic(traffic_raw),
                "traffic_label": traffic_raw.strip(),
                "source": "google-trends-trending-now-rss",
                "geo": geo,
            }
        )

    rows.sort(key=lambda row: row["traffic"], reverse=True)
    return rows


def _topic_tokens(topic: tuple) -> set[str]:
    key, display, query = topic[0], topic[1], topic[2]
    return tokens(f"{key.replace('-', ' ')} {display} {query}")


def score_topic_against_trend(topic: tuple, trend: dict) -> float:
    trend_query = str(trend.get("query", ""))
    trend_norm = normalise(trend_query)
    trend_tokens = tokens(trend_query)
    topic_tokens = _topic_tokens(topic)

    overlap = topic_tokens & trend_tokens
    if not overlap:
        return 0.0

    query_norm = normalise(topic[2])
    key_norm = normalise(str(topic[0]).replace("-", " "))
    exact_query = bool(query_norm and query_norm in trend_norm)
    exact_key = bool(key_norm and key_norm in trend_norm)

    if len(overlap) == 1 and not exact_query and not exact_key:
        only = next(iter(overlap))
        if only in WEAK_SINGLE_TOKENS:
            return 0.0

    traffic = max(int(trend.get("traffic") or 0), 100)
    traffic_score = min(30.0, math.log10(traffic) * 5.5)
    overlap_score = min(42.0, len(overlap) * 14.0)
    phrase_bonus = (24.0 if exact_query else 0.0) + (16.0 if exact_key else 0.0)

    return round(traffic_score + overlap_score + phrase_bonus, 2)


def rank_topics_by_trends(topics: list[tuple], market: str) -> list[tuple[tuple, dict]]:
    trends = fetch_trending_searches(market)
    if not trends:
        return []

    ranked: list[tuple[tuple, dict]] = []
    for topic in topics:
        best_signal: dict | None = None
        best_score = 0.0

        for trend in trends:
            score = score_topic_against_trend(topic, trend)
            if score > best_score:
                best_score = score
                best_signal = {**trend, "score": score}

        if best_signal is not None and best_score > 0:
            ranked.append((topic, best_signal))

    ranked.sort(
        key=lambda pair: (
            -float(pair[1].get("score") or 0),
            -int(pair[1].get("traffic") or 0),
            str(pair[0][0]),
        )
    )
    return ranked


def pretty_phrase(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", " ".join(str(value).split()))
    pretty: list[str] = []
    for word in words:
        mapped = PRETTY_WORDS.get(word.casefold())
        pretty.append(mapped if mapped else word.title())
    return " ".join(pretty)


def trend_keyword_for_title(topic: tuple, signal: dict | None) -> str | None:
    if not signal or float(signal.get("score") or 0) < 45:
        return None

    query = " ".join(str(signal.get("query") or "").split()).strip()
    if not query or len(query) > 70:
        return None

    query_words = normalise(query).split()
    if not (1 <= len(query_words) <= 7):
        return None
    if set(query_words) & BLOCKED_TITLE_TOKENS:
        return None

    trend_tokens = tokens(query)
    topic_tokens = _topic_tokens(topic)
    overlap = trend_tokens & topic_tokens
    query_norm = normalise(topic[2])
    key_norm = normalise(str(topic[0]).replace("-", " "))
    trend_norm = normalise(query)

    strong_match = (
        bool(query_norm and query_norm in trend_norm)
        or bool(key_norm and key_norm in trend_norm)
        or len(overlap) >= 2
        or (len(overlap) == 1 and next(iter(overlap)) not in WEAK_SINGLE_TOKENS)
    )
    if not strong_match:
        return None

    return pretty_phrase(query)
