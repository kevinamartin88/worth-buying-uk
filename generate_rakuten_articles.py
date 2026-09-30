from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from generate_daily_articles import (
    CATEGORY_CHECKS,
    EVERGREEN_HIGH_INTENT,
    SEASONAL_FALLBACKS,
    TOPICS,
)
from src.rakuten import RakutenClient, RakutenProduct


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "rakuten_article_generator.json"
MIN_PRODUCTS = 3
MAX_PRODUCTS = 5
MAX_SEARCHES_PER_MARKET = 24
RECENT_TOPIC_WINDOW = 45
QUERY_STOPWORDS = {"and", "best", "for", "home", "inch", "pro", "smart", "the", "with"}
PREFERRED_MERCHANTS = {
    "uk": (),
    "us": ("Sharper Image",),
}


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


def candidate_topics(month: int, recent_topics: list[str]) -> list[tuple]:
    by_key = {topic[0]: topic for topic in TOPICS}
    priority_keys = [
        *SEASONAL_FALLBACKS.get(month, ()),
        *EVERGREEN_HIGH_INTENT,
        *(topic[0] for topic in TOPICS),
    ]
    recent = set(recent_topics[-RECENT_TOPIC_WINDOW:])
    ordered: list[tuple] = []
    seen: set[str] = set()
    for key in priority_keys:
        if key in seen or key in recent or key not in by_key:
            continue
        ordered.append(by_key[key])
        seen.add(key)

    # Once every topic has been used recently, allow the oldest topics back in
    # instead of stopping the autonomous stream permanently.
    if not ordered:
        for key in recent_topics:
            if key in by_key and key not in seen:
                ordered.append(by_key[key])
                seen.add(key)
        for topic in TOPICS:
            if topic[0] not in seen:
                ordered.append(topic)
    return ordered


def relevant_products(products: list[RakutenProduct], query: str) -> list[RakutenProduct]:
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", query)
        if len(token) >= 3 and token.casefold() not in QUERY_STOPWORDS
    }
    if not tokens:
        return products

    matches: list[RakutenProduct] = []
    for product in products:
        name = product.name.casefold()
        if any(token in name for token in tokens):
            matches.append(product)
    return matches


def prioritize_products(products: list[RakutenProduct], market: str) -> list[RakutenProduct]:
    """Put approved preferred retailers first without excluding other good offers."""
    preferred = {name.casefold() for name in PREFERRED_MERCHANTS.get(market, ())}
    return sorted(products, key=lambda product: product.merchant.casefold() not in preferred)


def find_offer_set(
    client: RakutenClient,
    month: int,
    recent_topics: list[str],
    market: str = "",
) -> tuple[tuple | None, list[RakutenProduct]]:
    for topic in candidate_topics(month, recent_topics)[:MAX_SEARCHES_PER_MARKET]:
        products = relevant_products(client.search(topic[2], limit=12), topic[2])
        if len(products) >= MIN_PRODUCTS:
            return topic, prioritize_products(products, market)[:MAX_PRODUCTS]
    return None, []


def display_price(product: RakutenProduct, market: str) -> str:
    raw = product.price.strip()
    if not raw:
        return "Check the current retailer price"
    if any(char in raw for char in "£$") or re.search(r"[A-Za-z]", raw):
        return raw
    return f"{'£' if market == 'uk' else '$'}{raw}"


def product_sections(products: list[RakutenProduct], market: str) -> str:
    sections: list[str] = []
    for index, product in enumerate(products, start=1):
        sections.append(
            f"<h3>{index}. {html.escape(product.name)}</h3>\n"
            f"<p><strong>Retailer:</strong> {html.escape(product.merchant)}. "
            f"<strong>Price when checked:</strong> {html.escape(display_price(product, market))}. "
            "This product appeared in the approved retailer feed when this article was prepared. "
            "Check the exact model, specification, availability, delivery charge, warranty and returns "
            "on the live retailer page before ordering.</p>\n"
            f'<p><a href="{html.escape(product.url, quote=True)}" rel="sponsored nofollow">'
            f"View this offer at {html.escape(product.merchant)} (Ad)</a></p>"
        )
    return "\n".join(sections)


def build_article(topic: tuple, products: list[RakutenProduct], market: str, now: datetime) -> dict:
    key, display, query, _max_uk, _max_us, category, kicker = topic
    region = "UK" if market == "uk" else "USA"
    month_year = now.strftime("%B %Y")
    date_key = now.strftime("%Y-%m-%d")
    slug = f"approved-retailer-{key}-{market}-{date_key}"
    checks = CATEGORY_CHECKS.get(category, CATEGORY_CHECKS["Home & Kitchen"])
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)
    merchant_names = sorted({product.merchant for product in products})
    merchants = ", ".join(merchant_names)
    title = f"Current {display} Offers from Approved {region} Retailers ({month_year})"
    checked_date = now.strftime("%d %B %Y").lstrip("0")

    content = (
        f"<p><strong>We checked approved retailer feeds for current {html.escape(display.lower())} "
        f"offers available to {region} shoppers.</strong></p>\n"
        "<p><em>This is a separate Rakuten Advertising retailer roundup.</em></p>\n"
        f"<p><strong>Last checked:</strong> {html.escape(checked_date)}. The shortlist contains "
        f"{len(products)} live feed results from {html.escape(merchants)}. Prices and stock can change "
        "after publication.</p>\n"
        f"<h2>Current {html.escape(display.lower())} offers worth comparing</h2>\n"
        f"{product_sections(products, market)}\n"
        "<h2>How to compare these retailer offers</h2>\n"
        "<p>Start by matching the exact model number and specification, then compare the delivered price rather "
        "than the headline figure alone. A slightly higher price can represent better value when it includes a "
        "longer warranty, easier returns or useful accessories. Treat any advertised saving as context, not proof "
        "of value, and compare the live price before purchasing.</p>\n"
        f"<ul>{check_html}</ul>\n"
        "<h2>How this roundup was selected</h2>\n"
        f"<p>Our automation searched Rakuten Advertising product feeds belonging to retailers approved for the "
        f"Worth Buying {region} account. It required at least {MIN_PRODUCTS} relevant, region-appropriate results "
        "before creating this article. It did not copy recommendations from the separate Amazon and eBay guide, "
        "and it did not create an article when the feed was too limited.</p>\n"
        "<p>Feed inclusion is not the same as hands-on testing or a guarantee that a product is right for every "
        "buyer. Check independent reviews where performance, safety or durability is important.</p>"
    )

    return {
        "slug": slug,
        "source_sha": f"{date_key}-{key}-{market}-rakuten-v1",
        "mode": "publish",
        "title": title,
        "primary_category": category,
        "labels": [category, display, "Retailer Offers", "Rakuten", region],
        "ai_visual_enabled": True,
        "pinterest_enabled": True,
        "hero_image_kicker": f"{kicker} · RETAILER OFFERS",
        "pinterest_title": title,
        "pinterest_subtitle": "Approved retailer offers and practical checks before you buy",
        "x_image_title": f"Current {display} Offers",
        "x_kicker": "APPROVED RETAILER ROUNDUP",
        "x_subtitle": f"{region} offers checked in {month_year}",
        "x_text": (
            f"🔎 New retailer roundup: {display}\n\n"
            f"We checked approved {region} retailer feeds and found current offers worth comparing.\n\n"
            "See the separate roundup 👇\n"
            "Read the guide 🔗 {url}\n"
            "#Shopping #WorthBuying"
        ),
        "content_html": content,
        "_seo": {
            "version": "rakuten-retailer-roundup-v1",
            "primary_keyword": f"current {display.lower()} offers {region.lower()} {now.year}",
            "secondary_keywords": [
                f"{display.lower()} retailer offers",
                f"compare {display.lower()} {region.lower()}",
                f"{display.lower()} deals {month_year.lower()}",
            ],
            "description": (
                f"Compare current {display.lower()} offers from approved {region} retailers, with practical "
                "checks covering price, specification, warranty and returns."
            ),
            "search_intent": "commercial investigation",
        },
        "_generator": {
            "channel": "rakuten",
            "market": market,
            "topic": key,
            "query": query,
            "offer_count": len(products),
            "merchants": merchant_names,
            "article_directory": "articles" if market == "uk" else "articles-us",
        },
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    state = load_state()
    generated = 0

    for market in ("uk", "us"):
        market_state = state.get(market, {})
        if market_state.get("date") == today:
            print(f"[rakuten-skip] {market.upper()}: separate article already generated today")
            continue

        client = RakutenClient.for_market(market)
        if client is None:
            print(f"[rakuten-skip] {market.upper()}: credentials are not configured")
            continue

        recent_topics = list(market_state.get("recent_topics", []))
        try:
            topic, products = find_offer_set(client, now.month, recent_topics, market)
        except Exception as exc:
            print(f"[rakuten-skip] {market.upper()}: product search failed: {type(exc).__name__}: {exc}")
            continue

        if topic is None:
            print(
                f"[rakuten-skip] {market.upper()}: no topic returned at least "
                f"{MIN_PRODUCTS} relevant approved-retailer products"
            )
            continue

        article = build_article(topic, products, market, now)
        article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
        article_dir.mkdir(parents=True, exist_ok=True)
        output_path = article_dir / f"{article['slug']}.json"
        output_path.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        recent_topics.append(topic[0])
        state[market] = {
            "date": today,
            "slug": article["slug"],
            "topic": topic[0],
            "merchants": article["_generator"]["merchants"],
            "offer_count": len(products),
            "recent_topics": recent_topics[-RECENT_TOPIC_WINDOW:],
        }
        generated += 1
        print(
            f"[rakuten-created] {market.upper()}: {article['title']} "
            f"({len(products)} offers) -> {output_path.relative_to(ROOT)}"
        )

    if generated:
        save_state(state)
    print(f"Separate Rakuten article generation complete: {generated} article(s) created.")


if __name__ == "__main__":
    main()
