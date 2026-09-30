from __future__ import annotations

import argparse
import html
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

from googleapiclient.errors import HttpError

from generate_daily_articles import EVERGREEN_HIGH_INTENT, TOPICS
from src.blogger import BloggerClient
from src.ebay import EbayClient
from src.rakuten import RakutenClient


PAGE_TITLE = "Discount Codes"
NETWORKS = {"uk": 3, "us": 1}
EXPECTED_HOSTS = {
    "uk": {"www.worthbuyinguk.co.uk", "worthbuyinguk.co.uk", "worthbuyinguk.blogspot.com"},
    "us": {"www.worthbuyingusa.com", "worthbuyingusa.com", "worthbuyingusa.blogspot.com"},
}
MAX_OFFERS = 30
MAX_PER_ADVERTISER = 3
MAX_EBAY_SEARCHES = 10
DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%d/%m/%Y")


@dataclass(frozen=True)
class DiscountOffer:
    advertiser: str
    description: str
    url: str
    source: str
    code: str = ""
    restriction: str = ""
    start_date: str = ""
    end_date: str = ""


def parse_feed_date(value: str) -> date | None:
    raw = value.strip()
    if not raw or raw.casefold() in {"ongoing", "n/a", "none"}:
        return None
    raw = re.sub(r"(?:Z|[+-]\d\d:?\d\d)$", "", raw)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    return None


def active_offers(offers: list[DiscountOffer], today: date) -> list[DiscountOffer]:
    valid: list[DiscountOffer] = []
    for offer in offers:
        starts = parse_feed_date(offer.start_date)
        ends = parse_feed_date(offer.end_date)
        if starts and starts > today:
            continue
        if ends and ends < today:
            continue
        valid.append(offer)
    return valid


def select_offers(offers: list[DiscountOffer], today: date) -> list[DiscountOffer]:
    """Prefer genuine codes and variety, without inventing retailer popularity."""
    ranked = sorted(
        active_offers(offers, today),
        key=lambda offer: (
            not bool(offer.code),
            parse_feed_date(offer.end_date) or date.max,
            offer.advertiser.casefold(),
            offer.description.casefold(),
        ),
    )
    selected: list[DiscountOffer] = []
    counts: Counter[str] = Counter()
    for offer in ranked:
        merchant = offer.advertiser.casefold()
        if counts[merchant] >= MAX_PER_ADVERTISER:
            continue
        counts[merchant] += 1
        selected.append(offer)
        if len(selected) >= MAX_OFFERS:
            break
    return selected


def render_page(offers: list[DiscountOffer], market: str, today: date) -> str:
    region = "UK" if market == "uk" else "USA"
    intro = (
        f"<p><strong>Current discount codes and retailer offers for {region} shoppers.</strong> "
        "This page is refreshed weekly from official retailer and marketplace data available to Worth Buying. "
        "Codes, prices, availability and end dates can change, so confirm the offer on the retailer's "
        "website before ordering.</p>"
        f"<p><strong>Last updated:</strong> {today.strftime('%d %B %Y').lstrip('0')}.</p>"
    )
    if not offers:
        return intro + (
            "<div class=\"wb-code-empty\"><h2>No verified codes available this week</h2>"
            "<p>We found no current offers in the approved retailer feed. Please check again after the "
            "next weekly update.</p></div>"
        )

    cards: list[str] = []
    for offer in offers:
        end = parse_feed_date(offer.end_date)
        expiry = end.strftime("%d %B %Y").lstrip("0") if end else "Check retailer for end date"
        code_block = (
            f'<p class="wb-code"><span>Code</span> <code>{html.escape(offer.code)}</code></p>'
            if offer.code
            else '<p class="wb-code wb-no-code"><strong>No code required</strong></p>'
        )
        restriction = (
            f'<p class="wb-code-small"><strong>Conditions:</strong> {html.escape(offer.restriction)}</p>'
            if offer.restriction
            else ""
        )
        cards.append(
            '<article class="wb-code-card">'
            f"<h2>{html.escape(offer.advertiser)}</h2>"
            f'<p class="wb-code-source">Verified source: {html.escape(offer.source)}</p>'
            f"<p>{html.escape(offer.description)}</p>"
            f"{code_block}{restriction}"
            f'<p class="wb-code-small"><strong>Ends:</strong> {html.escape(expiry)}</p>'
            f'<p><a class="wb-code-button" href="{html.escape(offer.url, quote=True)}" '
            'rel="sponsored nofollow">View offer</a></p>'
            "</article>"
        )

    styles = """
<style>
.wb-code-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin:24px 0}
.wb-code-card{background:#fff;border:1px solid #dce6ef;border-top:4px solid #0aa89e;border-radius:14px;padding:20px;box-shadow:0 8px 22px rgba(7,38,79,.08)}
.wb-code-card h2{margin:0 0 10px;color:#082b63;font-size:1.25rem}.wb-code{background:#f1f7fa;border-radius:9px;padding:10px 12px}
.wb-code code{font-size:1.05rem;font-weight:700;color:#082b63;user-select:all}.wb-code-small{font-size:.9rem;color:#526274}
.wb-code-source{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:#087f78;font-weight:700}
.wb-code-button{display:inline-block;background:#087f78;color:#fff!important;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700}
.wb-code-button:hover{background:#066760}.wb-code-empty{background:#f1f7fa;border-radius:12px;padding:22px}
</style>"""
    return intro + styles + '<div class="wb-code-grid">' + "".join(cards) + "</div>"


def rakuten_offers(market: str) -> list[DiscountOffer]:
    client = RakutenClient.for_market(market)
    if client is None:
        raise RuntimeError(f"Rakuten {market.upper()} credentials are not configured")
    return [
        DiscountOffer(
            advertiser=offer.advertiser,
            description=offer.description,
            url=offer.url,
            source="Rakuten approved advertiser feed",
            code=offer.code,
            restriction=offer.restriction,
            start_date=offer.start_date,
            end_date=offer.end_date,
        )
        for offer in client.coupons(NETWORKS[market], limit=500)
    ]


def _safe_ebay_url(value: str, market: str) -> str:
    url = value.strip()
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    suffix = ".ebay.com" if market == "us" else ".ebay.co.uk"
    root_host = suffix[1:]
    if parts.scheme != "https" or parts.username or parts.password:
        return ""
    if host != root_host and not host.endswith(suffix):
        return ""
    return url


def ebay_offers(market: str) -> list[DiscountOffer]:
    client = EbayClient.for_market(market)
    topics = {topic[0]: topic for topic in TOPICS}
    candidates: list[DiscountOffer] = []
    seen_items: set[str] = set()
    for topic_key in EVERGREEN_HIGH_INTENT[:MAX_EBAY_SEARCHES]:
        topic = topics[topic_key]
        max_price = float(topic[3] if market == "uk" else topic[4])
        items = client.search(
            query=topic[2],
            max_price=max_price,
            require_free_shipping=False,
            affiliate_reference=f"discount-codes-{market}-{topic_key}",
            limit=20,
        )
        for item in items:
            item_id = str(item.get("itemId") or "")
            marketing = item.get("marketingPrice") or {}
            try:
                discount = float(marketing.get("discountPercentage") or 0)
                price = float((item.get("price") or {}).get("value"))
                original = float((marketing.get("originalPrice") or {}).get("value"))
            except (TypeError, ValueError):
                continue
            currency = str((item.get("price") or {}).get("currency") or "").upper()
            expected_currency = "GBP" if market == "uk" else "USD"
            url = _safe_ebay_url(
                str(item.get("itemAffiliateWebUrl") or item.get("itemWebUrl") or ""),
                market,
            )
            title = " ".join(str(item.get("title") or "").split())
            if (
                discount < 10
                or price <= 0
                or original <= price
                or currency != expected_currency
                or not item_id
                or item_id in seen_items
                or not title
                or not url
            ):
                continue
            seen_items.add(item_id)
            symbol = "£" if market == "uk" else "$"
            candidates.append(
                DiscountOffer(
                    advertiser="eBay",
                    description=f"{title} — {discount:.0f}% off ({symbol}{price:.2f}, was {symbol}{original:.2f})",
                    url=url,
                    source="eBay Browse API",
                    restriction="Listing price and stock can change; check the seller and delivery terms.",
                )
            )
    return candidates


def collect_offers(market: str) -> list[DiscountOffer]:
    collected: list[DiscountOffer] = []
    successful_sources = 0
    for name, loader in (("Rakuten", rakuten_offers), ("eBay", ebay_offers)):
        try:
            found = loader(market)
        except Exception as exc:
            print(f"[discount-source-skip] {market.upper()} {name}: {type(exc).__name__}: {exc}")
            continue
        successful_sources += 1
        collected.extend(found)
        print(f"[discount-source] {market.upper()} {name}: {len(found)} offer(s)")
    if not successful_sources:
        raise RuntimeError(f"Every discount source failed for {market.upper()}; existing page left untouched")
    return collected


def refresh_market(market: str) -> dict:
    today = datetime.now(timezone.utc).date()
    offers = select_offers(collect_offers(market), today)
    blogger = BloggerClient.from_env()
    blogger.resolve_blog(EXPECTED_HOSTS[market], f"Worth Buying {market.upper()}")
    content = render_page(offers, market, today)
    try:
        result = blogger.upsert_page(PAGE_TITLE, content)
        content_type = "page"
    except HttpError as exc:
        if getattr(exc.resp, "status", None) != 403:
            raise
        # Some otherwise-admin Blogger accounts can publish Posts but Google
        # rejects Pages API writes. Keep one stable, updateable post instead of
        # failing the autonomous weekly refresh or generating duplicates.
        print(
            f"[discount-codes] {market.upper()}: Blogger Pages write was forbidden; "
            "using one stable Discount Codes post"
        )
        result = blogger.upsert_post(
            PAGE_TITLE,
            content,
            labels=["Discount Codes", "Deals"],
        )
        content_type = "post"
    print(
        f"[discount-codes] {market.upper()}: refreshed {len(offers)} verified offer(s); "
        f"{content_type}={result.get('url', 'created/updated')}"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh a regional Blogger Discount Codes page")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    args = parser.parse_args()
    refresh_market(args.market)


if __name__ == "__main__":
    main()
