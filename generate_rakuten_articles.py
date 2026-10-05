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
    "uk": ("Choice Furniture Superstore", "Choice Furniture Supersto"),
    "us": ("Sharper Image",),
}
RETAILER_DISPLAY_NAMES = {
    # Rakuten shortens this advertiser name in some product-feed responses.
    "choice furniture supersto": "Choice Furniture Superstore",
}
RAKUTEN_ONLY_TOPICS = [
    ("dining-tables", "Dining Tables", "dining table", 1800, 2000, "Home & Kitchen", "DINING TABLE GUIDE"),
    ("coffee-tables", "Coffee Tables", "coffee table", 900, 1000, "Home & Kitchen", "COFFEE TABLE GUIDE"),
    ("bed-frames", "Bed Frames", "bed frame", 1600, 1800, "Home & Kitchen", "BED BUYING GUIDE"),
    ("wardrobes", "Wardrobes", "wardrobe", 1800, 2000, "Home & Kitchen", "WARDROBE GUIDE"),
    ("sideboards", "Sideboards", "sideboard", 1400, 1600, "Home & Kitchen", "SIDEBOARD GUIDE"),
]
RAKUTEN_TOPICS = [*RAKUTEN_ONLY_TOPICS, *TOPICS]
PREFERRED_TOPIC_KEYS = {
    "uk": tuple(topic[0] for topic in RAKUTEN_ONLY_TOPICS),
}
RETAILER_LOGO_ASSETS = {
    "sharper image": "assets/retailers/sharper-image.svg",
}

# Product-feed searches often return accessories whose titles happen to contain the
# parent product name (for example "hanging rail for sliding wardrobe"). These
# topic rules keep complete products separate from spares, refills and fittings.
TOPIC_PRODUCT_RULES = {
    "wardrobes": {
        "required_any": ("wardrobe", "armoire"),
        "exclude_any": (
            "hanging rail", "clothes rail", "garment rail", "wardrobe rail",
            "drawer insert", "shelf insert", "door track", "runner", "hinge",
            "handle", "bracket", "fitting", "spare", "replacement", "accessory",
            "organiser", "organizer",
        ),
        "min_price": 100.0,
    },
    "dining-tables": {
        "required_any": ("dining table",),
        "exclude_any": ("table leg", "table top only", "table cover", "protector", "extension leaf"),
        "min_price": 100.0,
    },
    "coffee-tables": {
        "required_any": ("coffee table",),
        "exclude_any": ("table leg", "table top only", "glass top only", "table cover"),
        "min_price": 40.0,
    },
    "bed-frames": {
        "required_any": ("bed frame", "bedstead", "platform bed"),
        "exclude_any": ("headboard", "replacement slat", "bed slat", "underbed drawer", "mattress"),
        "min_price": 100.0,
    },
    "sideboards": {
        "required_any": ("sideboard",),
        "exclude_any": ("handle", "replacement shelf", "leg set", "spare"),
        "min_price": 100.0,
    },
    "air-purifiers": {
        "required_any": ("air purifier", "air cleaner"),
        "exclude_any": ("filter", "refill", "replacement", "wire kit", "capsule"),
    },
    "coffee-machines": {
        "required_any": ("coffee machine", "coffee maker", "espresso machine"),
        "exclude_any": ("filter", "carafe", "capsule", "pod", "replacement", "accessory"),
    },
    "slow-cookers": {
        "required_any": ("slow cooker", "crock pot", "crock-pot"),
        "exclude_any": ("liner", "replacement lid", "replacement pot", "accessory"),
    },
}

FURNITURE_CHECKS = [
    "Measure the available space carefully and check the full product dimensions before ordering.",
    "Check the construction materials, finish, assembly requirements and whether wall fixing or anchoring is recommended.",
    "Confirm delivery access, included fittings, warranty and returns before committing to a bulky item.",
    "Compare the delivered price with another retailer rather than relying on the headline price alone.",
]
TOPIC_CHECKS = {
    "wardrobes": [
        "Check the overall width, height and depth against the available space, skirting and ceiling height.",
        "Confirm whether the doors are hinged or sliding and allow enough clearance for comfortable access.",
        "Compare the internal layout, including hanging space, shelves and drawers, and check which fittings are included.",
        "Check delivery access, assembly, wall-fixing guidance, materials, warranty and returns before ordering.",
    ],
    "dining-tables": FURNITURE_CHECKS,
    "coffee-tables": FURNITURE_CHECKS,
    "bed-frames": FURNITURE_CHECKS,
    "sideboards": FURNITURE_CHECKS,
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


def candidate_topics(month: int, recent_topics: list[str], market: str = "") -> list[tuple]:
    by_key = {topic[0]: topic for topic in RAKUTEN_TOPICS}
    priority_keys = [
        *PREFERRED_TOPIC_KEYS.get(market, ()),
        *SEASONAL_FALLBACKS.get(month, ()),
        *EVERGREEN_HIGH_INTENT,
        *(topic[0] for topic in RAKUTEN_TOPICS),
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
        for topic in RAKUTEN_TOPICS:
            if topic[0] not in seen:
                ordered.append(topic)
    return ordered


def _numeric_price(raw: str) -> float | None:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(raw or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _passes_topic_rule(product: RakutenProduct, topic_key: str) -> bool:
    rule = TOPIC_PRODUCT_RULES.get(topic_key)
    if not rule:
        return True

    name = " ".join(product.name.casefold().split())
    required = tuple(rule.get("required_any", ()))
    excluded = tuple(rule.get("exclude_any", ()))
    if required and not any(term in name for term in required):
        return False
    if excluded and any(term in name for term in excluded):
        return False

    minimum = rule.get("min_price")
    price = _numeric_price(product.price)
    if minimum is not None and price is not None and price < float(minimum):
        return False
    return True


def relevant_products(
    products: list[RakutenProduct],
    query: str,
    topic_key: str = "",
) -> list[RakutenProduct]:
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", query)
        if len(token) >= 3 and token.casefold() not in QUERY_STOPWORDS
    }

    matches: list[RakutenProduct] = []
    for product in products:
        name = product.name.casefold()
        if tokens and not any(token in name for token in tokens):
            continue
        if not _passes_topic_rule(product, topic_key):
            continue
        matches.append(product)
    return matches


def validate_offer_set(topic_key: str, products: list[RakutenProduct]) -> None:
    if topic_key not in TOPIC_PRODUCT_RULES:
        return
    invalid = [product.name for product in products if not _passes_topic_rule(product, topic_key)]
    if invalid:
        raise ValueError(
            f"Refusing to build {topic_key} roundup with off-topic/accessory products: "
            + "; ".join(invalid)
        )


def prioritize_products(products: list[RakutenProduct], market: str) -> list[RakutenProduct]:
    """Put approved preferred retailers first without excluding other good offers."""
    preferred = tuple(name.casefold() for name in PREFERRED_MERCHANTS.get(market, ()))

    def is_preferred(product: RakutenProduct) -> bool:
        merchant = product.merchant.casefold()
        return any(merchant == name or merchant.startswith(name) for name in preferred)

    return sorted(products, key=lambda product: not is_preferred(product))


def find_offer_set(
    client: RakutenClient,
    month: int,
    recent_topics: list[str],
    market: str = "",
) -> tuple[tuple | None, list[RakutenProduct]]:
    for topic in candidate_topics(month, recent_topics, market)[:MAX_SEARCHES_PER_MARKET]:
        products = relevant_products(client.search(topic[2], limit=12), topic[2], topic[0])
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


def retailer_display_name(name: str) -> str:
    clean = " ".join(str(name).split())
    return RETAILER_DISPLAY_NAMES.get(clean.casefold(), clean)


def product_sections(products: list[RakutenProduct], market: str) -> str:
    sections: list[str] = []
    for index, product in enumerate(products, start=1):
        merchant = retailer_display_name(product.merchant)
        sections.append(
            f"<h3>{index}. {html.escape(product.name)}</h3>\n"
            f"<p><strong>Retailer:</strong> {html.escape(merchant)}. "
            f"<strong>Price when checked:</strong> {html.escape(display_price(product, market))}. "
            "This product appeared in the approved retailer feed when this article was prepared. "
            "Check the exact model, specification, availability, delivery charge, warranty and returns "
            "on the live retailer page before ordering.</p>\n"
            f'<p><a href="{html.escape(product.url, quote=True)}" rel="sponsored nofollow">'
            f"View this offer at {html.escape(merchant)} (Ad)</a></p>"
        )
    return "\n".join(sections)


def build_article(topic: tuple, products: list[RakutenProduct], market: str, now: datetime) -> dict:
    key, display, query, _max_uk, _max_us, category, kicker = topic
    validate_offer_set(key, products)
    region = "UK" if market == "uk" else "USA"
    month_year = now.strftime("%B %Y")
    date_key = now.strftime("%Y-%m-%d")
    slug = f"approved-retailer-{key}-{market}-{date_key}"
    checks = TOPIC_CHECKS.get(key, CATEGORY_CHECKS.get(category, CATEGORY_CHECKS["Home & Kitchen"]))
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)
    merchant_names = sorted({retailer_display_name(product.merchant) for product in products})
    merchants = ", ".join(merchant_names)
    featured_retailer = merchant_names[0] if len(merchant_names) == 1 else ""
    retailer_logo_asset = RETAILER_LOGO_ASSETS.get(featured_retailer.casefold(), "")
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
        "source_sha": f"{date_key}-{key}-{market}-rakuten-v2",
        "mode": "publish",
        "title": title,
        "primary_category": category,
        "labels": [category, display, "Retailer Offers", "Rakuten", region],
        "ai_visual_enabled": True,
        "pinterest_enabled": True,
        "hero_image_kicker": f"{kicker} · RETAILER OFFERS",
        "featured_retailer": featured_retailer,
        "retailer_logo_asset": retailer_logo_asset,
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
            "featured_retailer": featured_retailer,
            "retailer_logo_asset": retailer_logo_asset,
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
