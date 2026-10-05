"""Live eBay deal discovery and validation; no cached prices qualify an offer."""
from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

from src.ebay import EbayClient, MARKETS
from publish_articles import UK_EPN_PARAMS, add_uk_epn_tracking
from publish_articles_us import US_EPN_PARAMS, add_us_epn_tracking

TRACKING = {"uk": UK_EPN_PARAMS, "us": US_EPN_PARAMS}
TITLES = {"uk": "Weekly eBay Deals UK", "us": "Weekly eBay Deals USA"}
MARKER = re.compile(r'<!-- wb-ebay-deals:(.*?) -->', re.S)
MAX_DEALS = 18
MAX_PER_TOPIC = 3
TOPICS = (
    ("laptops", "refurbished laptop", 500, 650),
    ("tablets", "tablet", 400, 500),
    ("vacuums", "cordless vacuum cleaner", 400, 500),
    ("air-fryers", "air fryer", 250, 300),
    ("drills", "cordless drill", 250, 300),
    ("headphones", "wireless headphones", 250, 300),
)
UNSUITABLE = re.compile(
    r'\b(for parts|spares|not working|faulty|broken|repair only|empty box|'
    r'box only|case only|cover only|replacement filter|replacement battery|'
    r'charger only|accessory|accessories|screen protector|case for|cover for)\b', re.I,
)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except ValueError:
        return None


def validate_item(item: dict, market: str, ceiling: float, now: datetime) -> dict | None:
    profile = MARKETS[market]
    price_info = item.get("price") or {}
    marketing = item.get("marketingPrice") or {}
    original_info = marketing.get("originalPrice") or {}
    price, original = number(price_info.get("value")), number(original_info.get("value"))
    advertised = number(marketing.get("discountPercentage"))
    if (price is None or original is None or advertised is None
            or not 0 < price <= ceiling or original <= price
            or price_info.get("currency") != profile.currency
            or original_info.get("currency") != profile.currency):
        return None
    discount = (original - price) / original * 100
    if not 10 <= discount < 100 or abs(discount - advertised) > 2:
        return None
    title = " ".join(str(item.get("title") or "").split())
    if not title or UNSUITABLE.search(title) or str(item.get("conditionId")) == "7000":
        return None
    if "FIXED_PRICE" not in (item.get("buyingOptions") or []):
        return None
    if item.get("listingMarketplaceId") != profile.marketplace:
        return None
    if (item.get("itemLocation") or {}).get("country") != profile.delivery_country:
        return None
    seller = item.get("seller") or {}
    feedback, count = number(seller.get("feedbackPercentage")), number(seller.get("feedbackScore"))
    if feedback is None or count is None or not 97 <= feedback <= 100 or count < 25:
        return None
    availability = item.get("estimatedAvailabilities") or []
    if not availability or any(
        entry.get("estimatedAvailabilityStatus") != "IN_STOCK"
        or (entry.get("estimatedAvailableQuantity") is not None
            and (number(entry["estimatedAvailableQuantity"]) or 0) <= 0)
        for entry in availability
    ):
        return None
    end = timestamp(item.get("itemEndDate")) if item.get("itemEndDate") else None
    if item.get("itemEndDate") and (end is None or end <= now + timedelta(days=1)):
        return None
    shipping = []
    for option in item.get("shippingOptions") or []:
        cost = option.get("shippingCost") or {}
        value = number(cost.get("value"))
        if cost.get("currency") == profile.currency and value is not None and value >= 0:
            shipping.append(value)
    if not shipping:
        return None
    url = str(item.get("itemWebUrl") or "")
    try:
        parts = urlsplit(url)
        host = "ebay.co.uk" if market == "uk" else "ebay.com"
        if (parts.scheme != "https" or parts.hostname not in {host, "www." + host}
                or parts.username or parts.password or parts.port not in {None, 443}
                or not parts.path.startswith("/itm/")):
            return None
    except ValueError:
        return None
    if not item.get("itemId"):
        return None
    return {
        "id": item["itemId"], "title": title, "url": url,
        "price": price, "original": original, "discount": discount,
        "shipping": min(shipping), "currency": profile.currency,
        "condition": str(item.get("condition") or "Check listing"),
        "end": end.isoformat() if end else "",
    }


def get_current(client, item_id, reference):
    try:
        item = client.get_item(item_id, reference)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in {404, 410}:
            return {}
        raise  # Authentication, quota and service failures must fail visibly.
    return item if item.get("itemId") == item_id else {}


def discover(client: EbayClient, market: str, now: datetime) -> list[dict]:
    selected, seen = [], set()
    for topic, query, uk_ceiling, us_ceiling in TOPICS:
        ceiling = uk_ceiling if market == "uk" else us_ceiling
        reference = f"weekly-deals-{market}-{topic}-{now:%Y%m%d}"
        summaries = client.search(query, ceiling, False, reference, limit=30)
        accepted = 0
        for summary in summaries:
            item_id = summary.get("itemId")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            # Only enrich plausible discounts; detail is the sole source of prices/stock.
            if (number((summary.get("marketingPrice") or {}).get("discountPercentage")) or 0) < 10:
                continue
            current = get_current(client, item_id, reference)
            deal = validate_item(current, market, ceiling, now)
            if deal:
                deal.update(topic=topic, ceiling=ceiling)
                selected.append(deal)
                accepted += 1
            if accepted >= MAX_PER_TOPIC:
                break
    return selected[:MAX_DEALS]


def revalidate(client, market, content, now):
    match = MARKER.search(content)
    if not match:
        raise ValueError("Existing roundup has no eBay deal metadata")
    metadata = json.loads(match.group(1))
    if metadata.get("market") != market:
        raise ValueError("Roundup market does not match publishing target")
    deals = []
    for record in metadata["items"][:MAX_DEALS]:
        item = get_current(client, record["id"], f"weekly-deals-{market}-{record['topic']}")
        deal = validate_item(item, market, record["ceiling"], now)
        if deal:
            deal.update(topic=record["topic"], ceiling=record["ceiling"])
            deals.append(deal)
    return deals, metadata["discovered_at"]


def render(deals, market, now, discovered_at):
    symbol = "£" if market == "uk" else "$"
    region = "UK" if market == "uk" else "USA"
    content = (
        f'<div class="wb-ebay-deals"><p><strong>Current eBay deals for {region} shoppers.</strong> '
        'New offers are selected weekly and checked daily for price and availability.</p>'
        f'<p>Offers refreshed: {html.escape(discovered_at[:10])}. '
        f'Last checked: {now:%d %B %Y %H:%M} UTC.</p>'
        '<p>These are eBay-listed discounts against the seller’s reference price, '
        'not independently verified historical savings. Prices and stock can change. '
        'Affiliate links may earn us commission at no extra cost to you.</p>'
    )
    for deal in deals:
        content += (
            f'<article><h2>{html.escape(deal["title"])}</h2>'
            f'<p><strong>{symbol}{deal["price"]:.2f}</strong> · '
            f'eBay reference price: {symbol}{deal["original"]:.2f} · '
            f'{deal["discount"]:.0f}% eBay-listed discount</p>'
            f'<p>Condition: {html.escape(deal["condition"])}. '
            f'Delivery from {symbol}{deal["shipping"]:.2f}; '
            'confirm delivery, tax, warranty and returns on the listing.</p>'
            f'<p><a href="{html.escape(deal["url"], quote=True)}" '
            'rel="sponsored nofollow noopener">Check current eBay price and availability</a></p></article>'
        )
    if not deals:
        content += '<p>No verified eBay deals currently qualify. Check again after the next weekly refresh.</p>'
    content += '</div>'
    tracker = add_uk_epn_tracking if market == "uk" else add_us_epn_tracking
    content = tracker(content, custom_id=f"weekly-ebay-deals-{market}")
    metadata = {"market": market, "discovered_at": discovered_at,
                "items": [{key: row[key] for key in ("id", "topic", "ceiling")} for row in deals]}
    encoded = json.dumps(metadata, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")
    return content + f'<!-- wb-ebay-deals:{encoded} -->'
