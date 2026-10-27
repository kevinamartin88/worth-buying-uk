from __future__ import annotations

import math
import re
from statistics import median


def _safe_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def item_price(item: dict):
    return _safe_float((item.get("price") or {}).get("value"))


def price_range_text(items: list[dict], market: str) -> str:
    prices = sorted(price for item in items if (price := item_price(item)) is not None and price > 0)
    if not prices:
        return ""
    symbol = "£" if market == "uk" else "$"
    low, high = prices[0], prices[-1]
    def fmt(value: float) -> str:
        return f"{symbol}{value:,.0f}" if value >= 20 else f"{symbol}{value:,.2f}"
    return fmt(low) if low == high else f"{fmt(low)}–{fmt(high)}"


def ctr_title(display: str, region: str, year: int, items: list[dict]) -> str:
    count = len(items)
    price_range = price_range_text(items, "uk" if region == "UK" else "us")
    if count >= 3 and price_range:
        return f"{count} Best {display} {region} {year}: Picks from {price_range}"
    if count >= 3:
        return f"{count} Best {display} {region} {year}: Worth Comparing"
    return f"Best {display} {region} {year}: What to Compare Before You Buy"


def ctr_description(display: str, region: str, year: int, items: list[dict]) -> str:
    market = "uk" if region == "UK" else "us"
    price_range = price_range_text(items, market)
    count = len(items)
    lead = f"Compare {count} current {display.lower()}" if count else f"Compare {display.lower()}"
    if price_range:
        lead += f" from {price_range}"
    text = (
        f"{lead} in the {region} for {year}, with Amazon and eBay checks, "
        "clear pros and trade-offs, buying advice and live retailer prices."
    )
    if len(text) <= 155:
        return text
    text = (
        f"{lead} in the {region}: Amazon and eBay checks, pros and trade-offs, "
        "buying advice and live retailer prices."
    )
    return text[:155].rstrip(" ,.;:-")


def worth_buying_score(item: dict, peers: list[dict], amazon_exact: bool = False) -> int:
    score = 58.0
    seller = item.get("seller") or {}
    feedback = _safe_float(seller.get("feedbackPercentage"))
    count = _safe_int(seller.get("feedbackScore"))
    if feedback is not None:
        if feedback >= 99.5:
            score += 12
        elif feedback >= 99.0:
            score += 9
        elif feedback >= 98.0:
            score += 5
    if count is not None:
        if count >= 10000:
            score += 7
        elif count >= 1000:
            score += 5
        elif count >= 250:
            score += 3

    prices = [p for row in peers if (p := item_price(row)) is not None and p > 0]
    price = item_price(item)
    if price is not None and prices:
        middle = median(prices)
        if price <= min(prices):
            score += 8
        elif price <= middle:
            score += 5

    condition = str(item.get("condition") or "").casefold()
    if "new" in condition and "refurb" not in condition:
        score += 4
    elif "refurb" in condition or "open box" in condition:
        score += 2

    history = item.get("_worthbuying_price_history") or {}
    observations = _safe_int(history.get("observations")) or 0
    difference = _safe_float(history.get("difference_pct")) or 0
    if observations >= 3 and difference >= 5:
        score += min(8, difference / 2)

    if amazon_exact:
        score += 7

    return max(50, min(98, int(round(score))))


def pick_badges(items: list[dict], amazon_exact_flags: list[bool] | None = None) -> list[str]:
    if not items:
        return []
    amazon_exact_flags = amazon_exact_flags or [False] * len(items)
    scores = [
        worth_buying_score(item, items, amazon_exact_flags[index] if index < len(amazon_exact_flags) else False)
        for index, item in enumerate(items)
    ]
    overall = max(range(len(items)), key=lambda i: scores[i])
    prices = [item_price(item) for item in items]
    priced = [i for i, value in enumerate(prices) if value is not None and value > 0]
    value = min(priced, key=lambda i: prices[i]) if priced else overall

    labels = ["Strong alternative"] * len(items)
    labels[overall] = "Best overall"
    if value != overall:
        labels[value] = "Best value"
    for i, exact in enumerate(amazon_exact_flags):
        if exact and i not in {overall, value}:
            labels[i] = "Best cross-retailer match"
            break
    return labels


def factual_pros_cons(item: dict, peers: list[dict], amazon_exact: bool = False) -> tuple[list[str], list[str]]:
    pros: list[str] = []
    cons: list[str] = []
    seller = item.get("seller") or {}
    feedback = _safe_float(seller.get("feedbackPercentage"))
    count = _safe_int(seller.get("feedbackScore"))
    if feedback is not None and feedback >= 99.0:
        pros.append(f"{feedback:.1f}% positive seller feedback when checked")
    if count is not None and count >= 1000:
        pros.append(f"Established seller history ({count:,} feedback entries)")

    price = item_price(item)
    peer_prices = [p for row in peers if (p := item_price(row)) is not None and p > 0]
    if price is not None and peer_prices and price <= median(peer_prices):
        pros.append("Priced at or below the shortlist median when checked")

    history = item.get("_worthbuying_price_history") or {}
    observations = _safe_int(history.get("observations")) or 0
    difference = _safe_float(history.get("difference_pct")) or 0
    if observations >= 3 and difference >= 5:
        pros.append(f"About {difference:.0f}% below its observed price median")

    if amazon_exact:
        pros.append("Exact Amazon product match verified by product identity")
    else:
        cons.append("No exact Amazon offer was verified, so the Amazon link is a focused product search")

    condition = str(item.get("condition") or "").strip()
    if condition and "new" not in condition.casefold():
        cons.append(f"Condition is listed as {condition}; check warranty and returns")
    if observations < 3:
        cons.append("Limited WorthBuying price history so far")

    if not pros:
        pros.append("Passed current price, seller-quality and product-relevance checks")
    if not cons:
        cons.append("Availability and retailer pricing can change after publication")
    return pros[:3], cons[:2]


def buyer_fit_copy(item: dict, amazon_exact: bool = False) -> tuple[str, str]:
    condition = str(item.get("condition") or "").casefold()
    if "refurb" in condition or "open box" in condition:
        best_for = "buyers comfortable with refurbished or open-box stock who prioritise value"
        avoid_if = "you only want factory-new stock with the simplest warranty route"
    elif amazon_exact:
        best_for = "buyers who want to compare the same identified product across Amazon and eBay"
        avoid_if = "you are still undecided on the specification or model you need"
    else:
        best_for = "buyers comparing current marketplace value before choosing a final retailer"
        avoid_if = "you need a verified like-for-like Amazon price before deciding"
    return best_for, avoid_if


BROAD_COMPETITION_KEYS = {
    "tvs", "laptops", "tablets", "headphones", "printers", "backpacks", "luggage",
}


def traffic_opportunity_score(
    topic_key: str,
    google_score: float,
    *,
    month: int,
    seasonal_keys: tuple[str, ...] = (),
    evergreen_keys: tuple[str, ...] = (),
    previously_covered: bool = False,
    query: str = "",
) -> float:
    """Blend live demand with commercial, seasonal and attainable-intent signals.

    This is a prioritisation heuristic, not a claimed Google ranking score.
    """
    demand = max(0.0, min(100.0, float(google_score or 0.0)))
    score = demand * 0.72
    score += 12.0 if topic_key in seasonal_keys else 3.0
    score += 9.0 if topic_key in evergreen_keys else 5.0
    score += 7.0 if previously_covered else 2.0
    if len(re.findall(r"[A-Za-z0-9]+", query)) >= 2:
        score += 5.0
    if topic_key in BROAD_COMPETITION_KEYS:
        score -= 8.0
    return round(max(0.0, min(100.0, score)), 2)
