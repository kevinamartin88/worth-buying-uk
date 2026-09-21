from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from src.ebay import EbayClient


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "daily_article_generator.json"

TOPICS = [
    ("tvs", "TVs", "4K smart TV", 1400, 1800, "Tech", "TV BUYING GUIDE"),
    ("cordless-vacuums", "Cordless Vacuum Cleaners", "cordless vacuum cleaner", 600, 700, "Home & Kitchen", "VACUUM BUYING GUIDE"),
    ("coffee-machines", "Coffee Machines", "coffee machine", 900, 1000, "Home & Kitchen", "COFFEE MACHINE GUIDE"),
    ("dehumidifiers", "Dehumidifiers", "dehumidifier", 450, 500, "Home & Kitchen", "DEHUMIDIFIER GUIDE"),
    ("robot-vacuums", "Robot Vacuum Cleaners", "robot vacuum cleaner", 900, 1000, "Home & Kitchen", "ROBOT VACUUM GUIDE"),
    ("soundbars", "Soundbars", "soundbar", 900, 1000, "Tech", "SOUNDBAR BUYING GUIDE"),
    ("monitors", "Computer Monitors", "27 inch monitor", 700, 800, "Tech", "MONITOR BUYING GUIDE"),
    ("dash-cams", "Dash Cams", "dash cam", 450, 500, "Motoring", "DASH CAM BUYING GUIDE"),
    ("wireless-earbuds", "Wireless Earbuds", "wireless earbuds", 350, 400, "Tech", "EARBUDS BUYING GUIDE"),
    ("smartwatches", "Smartwatches", "smartwatch", 700, 800, "Tech", "SMARTWATCH BUYING GUIDE"),
    ("tablets", "Tablets", "tablet", 1000, 1200, "Tech", "TABLET BUYING GUIDE"),
    ("blenders", "Blenders", "blender", 400, 450, "Home & Kitchen", "BLENDER BUYING GUIDE"),
    ("kettles", "Kettles", "electric kettle", 250, 300, "Home & Kitchen", "KETTLE BUYING GUIDE"),
    ("microwaves", "Microwaves", "microwave oven", 450, 500, "Home & Kitchen", "MICROWAVE BUYING GUIDE"),
    ("slow-cookers", "Slow Cookers", "slow cooker", 250, 300, "Home & Kitchen", "SLOW COOKER GUIDE"),
    ("stand-mixers", "Stand Mixers", "stand mixer", 800, 900, "Home & Kitchen", "STAND MIXER GUIDE"),
    ("food-processors", "Food Processors", "food processor", 500, 600, "Home & Kitchen", "FOOD PROCESSOR GUIDE"),
    ("steam-mops", "Steam Mops", "steam mop", 300, 350, "Home & Kitchen", "STEAM MOP GUIDE"),
    ("carpet-cleaners", "Carpet Cleaners", "carpet cleaner", 600, 700, "Home & Kitchen", "CARPET CLEANER GUIDE"),
    ("air-purifiers", "Air Purifiers", "air purifier", 600, 700, "Home & Kitchen", "AIR PURIFIER GUIDE"),
    ("tower-fans", "Tower Fans", "tower fan", 300, 350, "Home & Kitchen", "FAN BUYING GUIDE"),
    ("portable-heaters", "Portable Heaters", "portable electric heater", 250, 300, "Home & Kitchen", "HEATER BUYING GUIDE"),
    ("power-banks", "Power Banks", "USB C power bank", 180, 200, "Tech", "POWER BANK GUIDE"),
    ("usb-c-chargers", "USB-C Chargers", "USB C charger", 150, 180, "Tech", "CHARGER BUYING GUIDE"),
    ("keyboards", "Computer Keyboards", "computer keyboard", 300, 350, "Tech", "KEYBOARD BUYING GUIDE"),
    ("computer-mice", "Computer Mice", "computer mouse", 220, 250, "Tech", "MOUSE BUYING GUIDE"),
    ("webcams", "Webcams", "webcam", 250, 300, "Tech", "WEBCAM BUYING GUIDE"),
    ("printers", "Home Printers", "home printer", 450, 500, "Tech", "PRINTER BUYING GUIDE"),
    ("wifi-routers", "Wi-Fi Routers", "wifi router", 450, 500, "Tech", "WI-FI ROUTER GUIDE"),
    ("mesh-wifi", "Mesh Wi-Fi Systems", "mesh wifi system", 700, 800, "Tech", "MESH WI-FI GUIDE"),
    ("security-cameras", "Home Security Cameras", "home security camera", 500, 600, "Tech", "SECURITY CAMERA GUIDE"),
    ("video-doorbells", "Video Doorbells", "video doorbell", 350, 400, "Tech", "VIDEO DOORBELL GUIDE"),
    ("smart-plugs", "Smart Plugs", "smart plug", 120, 150, "Tech", "SMART PLUG GUIDE"),
    ("bluetooth-speakers", "Bluetooth Speakers", "bluetooth speaker", 450, 500, "Tech", "SPEAKER BUYING GUIDE"),
    ("projectors", "Home Projectors", "home projector", 1200, 1400, "Tech", "PROJECTOR BUYING GUIDE"),
    ("office-chairs", "Office Chairs", "office chair", 700, 800, "Home & Kitchen", "OFFICE CHAIR GUIDE"),
    ("luggage", "Luggage", "suitcase luggage", 450, 500, "Home & Kitchen", "LUGGAGE BUYING GUIDE"),
    ("backpacks", "Backpacks", "backpack", 250, 300, "Home & Kitchen", "BACKPACK BUYING GUIDE"),
    ("cordless-drills", "Cordless Drills", "cordless drill", 450, 500, "Home & Kitchen", "CORDLESS DRILL GUIDE"),
    ("pressure-washers", "Pressure Washers", "pressure washer", 700, 800, "Home & Kitchen", "PRESSURE WASHER GUIDE"),
    ("tool-sets", "Tool Sets", "tool set", 500, 600, "Motoring", "TOOL SET BUYING GUIDE"),
    ("tyre-inflators", "Tyre Inflators", "tyre inflator", 220, 250, "Motoring", "TYRE INFLATOR GUIDE"),
    ("jump-starters", "Car Jump Starters", "car jump starter", 300, 350, "Motoring", "JUMP STARTER GUIDE"),
    ("car-vacuums", "Car Vacuum Cleaners", "car vacuum cleaner", 180, 200, "Motoring", "CAR VACUUM GUIDE"),
    ("car-phone-mounts", "Car Phone Mounts", "car phone mount", 120, 150, "Motoring", "CAR PHONE MOUNT GUIDE"),
    ("battery-chargers", "Car Battery Chargers", "car battery charger", 250, 300, "Motoring", "BATTERY CHARGER GUIDE"),
    ("gaming-headsets", "Gaming Headsets", "gaming headset", 350, 400, "Gaming", "GAMING HEADSET GUIDE"),
    ("gaming-keyboards", "Gaming Keyboards", "gaming keyboard", 350, 400, "Gaming", "GAMING KEYBOARD GUIDE"),
    ("gaming-mice", "Gaming Mice", "gaming mouse", 250, 300, "Gaming", "GAMING MOUSE GUIDE"),
    ("game-controllers", "Game Controllers", "gaming controller", 220, 250, "Gaming", "CONTROLLER BUYING GUIDE"),
    ("ssds", "Solid-State Drives", "SSD drive", 600, 700, "Tech", "SSD BUYING GUIDE"),
    ("external-hard-drives", "External Hard Drives", "external hard drive", 500, 600, "Tech", "STORAGE BUYING GUIDE"),
    ("mini-pcs", "Mini PCs", "mini PC", 900, 1000, "Tech", "MINI PC BUYING GUIDE"),
    ("headphones", "Headphones", "headphones", 600, 700, "Tech", "HEADPHONE BUYING GUIDE"),
    ("hair-dryers", "Hair Dryers", "hair dryer", 450, 500, "Home & Kitchen", "HAIR DRYER GUIDE"),
    ("electric-toothbrushes", "Electric Toothbrushes", "electric toothbrush", 350, 400, "Home & Kitchen", "TOOTHBRUSH BUYING GUIDE"),
    ("electric-shavers", "Electric Shavers", "electric shaver", 450, 500, "Home & Kitchen", "SHAVER BUYING GUIDE"),
    ("hair-straighteners", "Hair Straighteners", "hair straightener", 350, 400, "Home & Kitchen", "HAIR STYLING GUIDE"),
    ("rice-cookers", "Rice Cookers", "rice cooker", 300, 350, "Home & Kitchen", "RICE COOKER GUIDE"),
    ("multicookers", "Multicookers", "multicooker", 500, 600, "Home & Kitchen", "MULTICOOKER GUIDE"),
    ("juicers", "Juicers", "juicer", 400, 450, "Home & Kitchen", "JUICER BUYING GUIDE"),
    ("ice-makers", "Countertop Ice Makers", "countertop ice maker", 450, 500, "Home & Kitchen", "ICE MAKER GUIDE"),
    ("bread-makers", "Bread Makers", "bread maker", 350, 400, "Home & Kitchen", "BREAD MAKER GUIDE"),
    ("electric-blankets", "Electric Blankets", "electric blanket", 180, 220, "Home & Kitchen", "ELECTRIC BLANKET GUIDE"),
    ("leaf-blowers", "Leaf Blowers", "leaf blower", 450, 500, "Home & Kitchen", "LEAF BLOWER GUIDE"),
    ("hedge-trimmers", "Hedge Trimmers", "hedge trimmer", 450, 500, "Home & Kitchen", "HEDGE TRIMMER GUIDE"),
    ("lawn-mowers", "Lawn Mowers", "lawn mower", 900, 1000, "Home & Kitchen", "LAWN MOWER GUIDE"),
    ("storage-bins", "Storage Bins & Organisers", "storage bins organizer", 180, 220, "Home & Kitchen", "HOME ORGANISATION GUIDE"),
    ("non-slip-hangers", "Non-Slip Hangers", "non slip hangers", 120, 150, "Home & Kitchen", "HOME ORGANISATION GUIDE"),
    ("cleaning-bundles", "Multi-Purpose Cleaning Bundles", "household cleaning bundle", 180, 220, "Home & Kitchen", "CLEANING BUYING GUIDE"),
    ("portable-griddles", "Portable Griddles", "portable griddle", 700, 800, "Home & Kitchen", "OUTDOOR COOKING GUIDE"),
    ("smart-light-switches", "Smart Light Switches", "smart light switch", 220, 260, "Tech", "SMART HOME GUIDE"),
    ("apple-watches", "Apple Watches", "Apple Watch", 900, 1000, "Tech", "APPLE WATCH BUYING GUIDE"),
    ("airpods", "AirPods & Wireless Earbuds", "Apple AirPods wireless earbuds", 450, 500, "Tech", "EARBUDS BUYING GUIDE"),
    ("streaming-devices", "Streaming Devices", "Fire TV Roku streaming device", 220, 250, "Tech", "STREAMING DEVICE GUIDE"),
    ("portable-gaming-systems", "Portable Gaming Systems", "handheld gaming console", 900, 1000, "Gaming", "PORTABLE GAMING GUIDE"),
    ("loungewear", "Comfortable Loungewear", "loungewear set", 220, 250, "Home & Kitchen", "LIFESTYLE BUYING GUIDE"),
    ("beauty-sets", "Beauty & Self-Care Sets", "beauty self care set", 220, 250, "Home & Kitchen", "BEAUTY BUYING GUIDE"),
    ("seasonal-hobby-kits", "Seasonal Hobby & Craft Kits", "craft hobby kit", 220, 250, "Home & Kitchen", "HOBBY BUYING GUIDE"),
    ("garden-tool-sets", "Garden Tool Sets", "garden tool set", 300, 350, "Home & Kitchen", "GARDEN TOOL GUIDE"),
]

SATURDAY_PRIORITY = (
    "storage-bins",
    "cleaning-bundles",
    "non-slip-hangers",
    "cordless-vacuums",
    "robot-vacuums",
    "steam-mops",
    "carpet-cleaners",
    "pressure-washers",
    "cordless-drills",
    "tool-sets",
    "garden-tool-sets",
    "lawn-mowers",
    "hedge-trimmers",
    "leaf-blowers",
    "portable-griddles",
    "smart-light-switches",
)

SUNDAY_PRIORITY = (
    "storage-bins",
    "non-slip-hangers",
    "cleaning-bundles",
    "robot-vacuums",
    "air-purifiers",
    "apple-watches",
    "airpods",
    "streaming-devices",
    "portable-gaming-systems",
    "gaming-headsets",
    "bluetooth-speakers",
    "loungewear",
    "beauty-sets",
    "seasonal-hobby-kits",
    "smart-light-switches",
)


CATEGORY_CHECKS = {
    "Tech": [
        "Check the exact model number and generation rather than relying on the headline product name.",
        "Compare warranty, condition and returns, especially for refurbished or open-box items.",
        "Confirm ports, connectivity and compatibility with the devices you already own.",
        "Compare the live price with at least one other retailer before buying.",
    ],
    "Home & Kitchen": [
        "Measure the space available and check the full product dimensions before ordering.",
        "Look at capacity, power use and cleaning or maintenance requirements, not just headline features.",
        "Check warranty, returns and whether replacement parts or consumables are easy to obtain.",
        "Compare the live price with another retailer before buying.",
    ],
    "Motoring": [
        "Check vehicle compatibility and fitment carefully before ordering.",
        "For safety-related equipment, prioritise clear specifications, warranty and a reputable seller.",
        "Check what is included in the box because accessories and adapters can vary by listing.",
        "Compare the live price and returns policy before buying.",
    ],
    "Gaming": [
        "Confirm platform and device compatibility before ordering.",
        "Compare wired versus wireless connectivity, battery life and included accessories.",
        "For used or refurbished products, check condition, warranty and controller or cable inclusions.",
        "Compare the live price with another retailer before buying.",
    ],
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def topic_already_covered(article_dir: Path, display: str, year: int) -> bool:
    wanted = normalise(display)
    for path in article_dir.glob("*.json"):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        title = str(article.get("title", ""))
        if str(year) in title and wanted and wanted in normalise(title):
            return True
    return False


def pick_topic(article_dir: Path, year: int, weekday: int) -> tuple:
    topic_by_key = {topic[0]: topic for topic in TOPICS}

    # Saturday/Sunday prioritise leisure-hour shopping themes: cleaning,
    # organisation, DIY, yard care, entertainment and lifestyle.
    weekend_priority = ()
    if weekday == 5:
        weekend_priority = SATURDAY_PRIORITY
    elif weekday == 6:
        weekend_priority = SUNDAY_PRIORITY

    for key in weekend_priority:
        topic = topic_by_key.get(key)
        if topic and not topic_already_covered(article_dir, topic[1], year):
            return topic

    # Once the weekend-priority pool is exhausted, or on weekdays, continue
    # through the normal high-intent rotation.
    for topic in TOPICS:
        if not topic_already_covered(article_dir, topic[1], year):
            return topic

    raise RuntimeError(
        "The curated daily-topic pool has been exhausted for this year. "
        "Add more topics before continuing automated publication."
    )


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def listing_score(item: dict, max_price: float, expected_currency: str) -> float | None:
    title = str(item.get("title", "")).casefold()
    blocked = (
        "for parts",
        "not working",
        "empty box",
        "box only",
        "manual only",
        "spares repair",
    )
    if any(term in title for term in blocked):
        return None

    price = safe_float((item.get("price") or {}).get("value"))
    currency = str((item.get("price") or {}).get("currency", ""))
    if price is None or price <= 0 or price > max_price or currency != expected_currency:
        return None

    buying_options = item.get("buyingOptions") or []
    if buying_options and "FIXED_PRICE" not in buying_options:
        return None

    seller = item.get("seller") or {}
    feedback_pct = safe_float(seller.get("feedbackPercentage"))
    feedback_count = safe_int(seller.get("feedbackScore"))

    if feedback_pct is not None and feedback_pct < 97.0:
        return None
    if feedback_count is not None and feedback_count < 25:
        return None

    score = 40.0

    if feedback_pct is not None:
        if feedback_pct >= 99.5:
            score += 16
        elif feedback_pct >= 99.0:
            score += 13
        elif feedback_pct >= 98.0:
            score += 9
        else:
            score += 5

    if feedback_count is not None:
        if feedback_count >= 10_000:
            score += 8
        elif feedback_count >= 1_000:
            score += 6
        elif feedback_count >= 250:
            score += 4
        elif feedback_count >= 50:
            score += 2

    marketing = item.get("marketingPrice") or {}
    discount = safe_float(marketing.get("discountPercentage"))
    if discount and discount > 0:
        score += min(discount, 20)

    ratio = price / max_price if max_price else 1
    if ratio <= 0.45:
        score += 7
    elif ratio <= 0.65:
        score += 5
    elif ratio <= 0.80:
        score += 3

    condition = str(item.get("condition", "")).casefold()
    if "new" in condition:
        score += 2

    return round(score, 2)


def current_picks(market: str, query: str, max_price: float, slug: str) -> list[dict]:
    expected_currency = "GBP" if market == "uk" else "USD"
    client = EbayClient.for_market(market)
    results = client.search(
        query=query,
        max_price=max_price,
        require_free_shipping=False,
        affiliate_reference=f"daily-{slug}"[:256],
        limit=40,
    )

    scored: list[tuple[float, dict]] = []
    seen: set[str] = set()

    for item in results:
        score = listing_score(item, max_price, expected_currency)
        if score is None:
            continue

        fingerprint = " ".join(normalise(str(item.get("title", ""))).split()[:8])
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:4]]


def retailer_urls(item: dict, market: str, fallback_query: str) -> tuple[str, str]:
    title = " ".join(str(item.get("title", "")).split())
    query = title[:120] or fallback_query

    ebay_url = str(item.get("itemAffiliateWebUrl") or item.get("itemWebUrl") or "").strip()
    if not ebay_url:
        base = "https://www.ebay.co.uk/sch/i.html" if market == "uk" else "https://www.ebay.com/sch/i.html"
        ebay_url = f"{base}?_nkw={quote_plus(fallback_query)}&_sop=15"

    amazon_base = "https://www.amazon.co.uk/s" if market == "uk" else "https://www.amazon.com/s"
    amazon_url = f"{amazon_base}?k={quote_plus(query)}"
    return ebay_url, amazon_url


def seller_text(item: dict) -> str:
    seller = item.get("seller") or {}
    feedback_pct = safe_float(seller.get("feedbackPercentage"))
    feedback_count = safe_int(seller.get("feedbackScore"))
    if feedback_pct is None:
        return "Seller feedback was not available in the API response, so check the live listing before buying."
    if feedback_count is None:
        return f"The seller feedback shown by eBay was {feedback_pct:.1f}% when this guide was generated."
    return (
        f"The seller feedback shown by eBay was {feedback_pct:.1f}% "
        f"from {feedback_count:,} feedback entries when this guide was generated."
    )


def price_text(item: dict, market: str) -> str:
    price = safe_float((item.get("price") or {}).get("value"))
    if price is None:
        return ""
    symbol = "£" if market == "uk" else "$"
    return f"{symbol}{price:,.2f}"


def discount_text(item: dict) -> str:
    discount = safe_float((item.get("marketingPrice") or {}).get("discountPercentage"))
    if discount and discount > 0:
        return (
            f" eBay was showing a listed discount of about {discount:.0f}% on this item "
            "when the article was generated."
        )
    return ""


def live_sections(items: list[dict], market: str, topic_name: str, query: str) -> str:
    parts: list[str] = []
    retailer = "eBay UK" if market == "uk" else "eBay"
    amazon = "Amazon UK" if market == "uk" else "Amazon"

    for index, item in enumerate(items, start=1):
        title = " ".join(str(item.get("title", "")).split())
        safe_title = html.escape(title)
        price = price_text(item, market)
        ebay_url, amazon_url = retailer_urls(item, market, query)

        parts.append(
            f"<h2>{index}. {safe_title}</h2>\n"
            f"<p><strong>Price when checked:</strong> {html.escape(price) if price else 'Check the live listing'}. "
            f"This current listing appeared near the top of our filtered {html.escape(topic_name)} search "
            "after basic price, fixed-price and seller-quality checks."
            f"{html.escape(discount_text(item))}</p>\n"
            f"<p>{html.escape(seller_text(item))} Availability, condition and price can change quickly, "
            "so verify the exact model, specification, warranty and returns on the retailer page.</p>\n"
            f'<p><a href="{html.escape(ebay_url, quote=True)}" rel="sponsored nofollow">'
            f"View on {retailer}</a>\n"
            f'<a href="{html.escape(amazon_url, quote=True)}" rel="sponsored nofollow">'
            f"Compare on {amazon}</a></p>\n"
        )

    return "\n".join(parts)


def fallback_sections(market: str, topic_name: str, query: str) -> str:
    ebay_base = "https://www.ebay.co.uk/sch/i.html" if market == "uk" else "https://www.ebay.com/sch/i.html"
    amazon_base = "https://www.amazon.co.uk/s" if market == "uk" else "https://www.amazon.com/s"
    retailer = "eBay UK" if market == "uk" else "eBay"
    amazon = "Amazon UK" if market == "uk" else "Amazon"

    variants = [
        ("Best-value options", query),
        ("Higher-spec options", f"{query} premium"),
        ("Refurbished and open-box options", f"refurbished {query}"),
        ("Popular current listings", f"{query} best seller"),
    ]

    parts: list[str] = []
    for index, (heading, search_query) in enumerate(variants, start=1):
        ebay_url = f"{ebay_base}?_nkw={quote_plus(search_query)}&_sop=15"
        amazon_url = f"{amazon_base}?k={quote_plus(search_query)}"
        parts.append(
            f"<h2>{index}. {html.escape(heading)}</h2>\n"
            f"<p>Compare current {html.escape(topic_name)} listings in this part of the market. "
            "The live retailer pages are the best place to check current models, prices, seller details "
            "and availability.</p>\n"
            f'<p><a href="{html.escape(ebay_url, quote=True)}" rel="sponsored nofollow">'
            f"Compare on {retailer}</a>\n"
            f'<a href="{html.escape(amazon_url, quote=True)}" rel="sponsored nofollow">'
            f"Compare on {amazon}</a></p>\n"
        )
    return "\n".join(parts)


def build_article(topic: tuple, market: str, year: int) -> dict:
    key, display, query, max_uk, max_us, category, kicker = topic
    region = "UK" if market == "uk" else "USA"
    directory_name = "articles" if market == "uk" else "articles-us"
    max_price = float(max_uk if market == "uk" else max_us)
    slug = f"best-{key}-worth-buying-{market}-{year}"

    try:
        picks = current_picks(market, query, max_price, slug)
    except Exception as exc:
        print(f"[daily-warning] {market.upper()} eBay lookup failed for {display}: {type(exc).__name__}: {exc}")
        picks = []

    live = len(picks) >= 3
    sections = (
        live_sections(picks, market, display, query)
        if live
        else fallback_sections(market, display, query)
    )

    checks = CATEGORY_CHECKS.get(category, CATEGORY_CHECKS["Home & Kitchen"])
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)

    title = f"Best {display} Worth Buying in the {region} ({year})"
    source_sha = f"{datetime.now(timezone.utc).date().isoformat()}-{key}-{market}-daily-v1"

    methodology = (
        f"For this daily guide, our automation searched current {('eBay UK' if market == 'uk' else 'eBay')} "
        f"listings for {html.escape(display)} and applied basic fixed-price, price-ceiling and seller-feedback checks. "
        "These are current marketplace picks rather than hands-on laboratory test results."
        if live
        else
        f"Our live marketplace lookup did not return enough listings that passed the automated filters today, "
        f"so this guide links to current retailer searches for {html.escape(display)} instead of inventing product recommendations."
    )

    content = (
        f"<p>{html.escape(display)} can vary widely in price and specification, so the best value depends on "
        "the features you will actually use, the exact model and the retailer terms available today.</p>\n"
        "<p><em>Some links in this article are affiliate links. We may earn a commission if you make a purchase, "
        "at no extra cost to you.</em></p>\n"
        f"<p>{methodology} Prices and availability can change after publication, so always verify the live listing.</p>\n"
        f"{sections}\n"
        "<h2>What to check before you buy</h2>\n"
        f"<ul>{check_html}</ul>\n"
        "<h2>How we use these daily picks</h2>\n"
        "<p>We use retailer data to narrow down products worth comparing, but we do not treat seller marketing claims "
        "or a displayed discount as proof that a product is objectively the best. Check independent reviews for the exact "
        "model if performance, safety or long-term reliability is especially important to your purchase.</p>\n"
        "<p><em>Prices, promotions, seller feedback and availability change regularly. Always check the live retailer page "
        "before purchasing.</em></p>\n"
        "<hr>\n"
        f"<p><strong>Affiliate disclosure:</strong> This article contains affiliate links. If you buy through one of these "
        f"links, Worth Buying {region} may earn a commission at no extra cost to you.</p>"
    )

    return {
        "slug": slug,
        "source_sha": source_sha,
        "mode": "publish",
        "title": title,
        "primary_category": category,
        "labels": [category, display, "Buying Guides", region],
        "ai_visual_enabled": True,
        "pinterest_enabled": True,
        "hero_image_kicker": kicker,
        "pinterest_title": title,
        "pinterest_subtitle": f"Current {display.lower()} worth comparing before you buy",
        "x_image_title": f"Best {display} Worth Buying",
        "x_kicker": kicker,
        "x_subtitle": f"Current {display.lower()} worth comparing in {year}",
        "x_text": (
            f"🔎 Looking for {display.lower()} worth comparing?\n\n"
            f"Our latest {region} guide checks current marketplace options, seller details and value.\n\n"
            "See the full guide 👇\n"
            "Ad/Affiliate 🔗 {url}\n"
            "#BuyingGuide #WorthBuying"
        ),
        "content_html": content,
        "_generator": {
            "market": market,
            "topic": key,
            "live_ebay_picks": live,
            "pick_count": len(picks),
            "article_directory": directory_name,
        },
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    year = now.year
    weekday = now.weekday()
    day_name = now.strftime("%A")
    is_weekend = weekday in (5, 6)
    state = load_json(STATE_PATH)
    generated = 0

    for market in ("uk", "us"):
        market_state = state.get(market, {})
        if market_state.get("date") == today:
            print(
                f"[daily-skip] {market.upper()}: article already generated today "
                f"({market_state.get('slug')})"
            )
            continue

        article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
        article_dir.mkdir(parents=True, exist_ok=True)

        topic = pick_topic(article_dir, year, weekday)
        article = build_article(topic, market, year)
        target = article_dir / f"{article['slug']}.json"
        if target.exists():
            raise RuntimeError(f"Refusing to overwrite existing article: {target}")

        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state[market] = {
            "date": today,
            "slug": article["slug"],
            "title": article["title"],
            "topic": topic[0],
            "day": day_name,
            "weekend_priority": is_weekend,
            "live_ebay_picks": bool(article["_generator"]["live_ebay_picks"]),
            "pick_count": int(article["_generator"]["pick_count"]),
        }
        generated += 1
        print(
            f"[daily-created] {market.upper()}: {target.relative_to(ROOT)} "
            f"(day={day_name}, weekend_priority={is_weekend}, "
            f"live eBay picks={article['_generator']['pick_count']})"
        )

    save_json(STATE_PATH, state)
    print(f"Daily article generation complete: {generated} article(s) created.")


if __name__ == "__main__":
    main()
