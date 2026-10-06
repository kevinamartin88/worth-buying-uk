from __future__ import annotations

import html
import json
import math
import os
import re
from datetime import date, datetime, timezone
from statistics import median
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from src.amazon_creators import AmazonCreatorsClient
from src.ebay import EbayClient
from src.product_image_quality import product_image_html
from src.price_tracking import refresh_tracked_prices
from src.google_trends import rank_topics_by_trends, trend_keyword_for_title
from src.google_shopping_trends import rank_topics_by_google_shopping
from src.usa_conversion import (
    relevant_product, live_listing, cards_html, amazon_direct, tracking_script, EXPERIMENT,
)


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "daily_article_generator.json"
PRICE_HISTORY_PATH = ROOT / "state" / "daily_price_history.json"
REFRESH_AFTER_DAYS = 21
LONDON_TZ = ZoneInfo("Europe/London")

# Do not publish a daily article merely because it is next in a curated list.
# At least one current Google-derived demand signal must clear these thresholds.
MIN_FRESH_TREND_SCORE = 55.0
MIN_TREND_DEMAND_SCORE = 40.0
MIN_GSC_DEMAND_SCORE = 50.0
MIN_GSC_IMPRESSIONS = 10.0
MIN_COMBINED_DEMAND_SCORE = 40.0


# If live Google signals are weak or unavailable, we still publish every day.
# The fallback order is seasonal first, then evergreen high-intent shopping.
SEASONAL_FALLBACKS = {
    1: ("portable-heaters", "electric-blankets", "dehumidifiers", "air-purifiers", "coffee-machines", "slow-cookers", "jump-starters", "battery-chargers"),
    2: ("portable-heaters", "electric-blankets", "dehumidifiers", "air-purifiers", "coffee-machines", "jump-starters", "battery-chargers", "robot-vacuums"),
    3: ("pressure-washers", "garden-tool-sets", "cordless-drills", "storage-bins", "steam-mops", "carpet-cleaners", "air-purifiers", "robot-vacuums"),
    4: ("lawn-mowers", "garden-tool-sets", "hedge-trimmers", "pressure-washers", "cordless-drills", "storage-bins", "carpet-cleaners", "robot-vacuums"),
    5: ("lawn-mowers", "hedge-trimmers", "garden-tool-sets", "pressure-washers", "portable-griddles", "tower-fans", "luggage", "power-banks"),
    6: ("tower-fans", "portable-griddles", "luggage", "power-banks", "bluetooth-speakers", "car-phone-mounts", "dash-cams", "portable-gaming-systems"),
    7: ("tower-fans", "portable-griddles", "luggage", "power-banks", "bluetooth-speakers", "car-phone-mounts", "dash-cams", "portable-gaming-systems"),
    8: ("tower-fans", "luggage", "power-banks", "backpacks", "printers", "tablets", "laptops", "wireless-earbuds"),
    9: ("dehumidifiers", "portable-heaters", "electric-blankets", "dash-cams", "jump-starters", "battery-chargers", "air-purifiers", "coffee-machines", "slow-cookers"),
    10: ("dehumidifiers", "portable-heaters", "electric-blankets", "jump-starters", "battery-chargers", "dash-cams", "air-purifiers", "coffee-machines", "slow-cookers"),
    11: ("portable-heaters", "electric-blankets", "dehumidifiers", "jump-starters", "battery-chargers", "air-fryers", "large-capacity-air-fryers", "coffee-machines", "gaming-headsets"),
    12: ("portable-heaters", "electric-blankets", "dehumidifiers", "air-fryers", "large-capacity-air-fryers", "coffee-machines", "gaming-headsets", "bluetooth-speakers", "streaming-devices"),
}

EVERGREEN_HIGH_INTENT = (
    "air-fryers",
    "large-capacity-air-fryers",
    "cordless-vacuums",
    "robot-vacuums",
    "coffee-machines",
    "tvs",
    "soundbars",
    "wireless-earbuds",
    "smartwatches",
    "tablets",
    "dash-cams",
    "power-banks",
    "security-cameras",
    "video-doorbells",
    "pressure-washers",
    "cordless-drills",
    "tyre-inflators",
    "jump-starters",
    "battery-chargers",
    "gaming-headsets",
)


# Concentrate publishing into a handful of commercial clusters so WorthBuying
# builds topical authority instead of scattering one-off articles everywhere.
# These clusters also map cleanly to products people commonly buy online.
AUTHORITY_CLUSTERS = {
    "Kitchen & Small Appliances": (
        "air-fryers", "large-capacity-air-fryers", "coffee-machines",
        "food-processors", "slow-cookers", "blenders", "stand-mixers",
    ),
    "Cleaning & Home Climate": (
        "cordless-vacuums", "robot-vacuums", "dehumidifiers", "air-purifiers",
        "portable-heaters", "electric-blankets", "carpet-cleaners", "steam-mops",
        "storage-bins", "non-slip-hangers",
    ),
    "Consumer Tech": (
        "tvs", "soundbars", "wireless-earbuds", "smartwatches", "tablets",
        "power-banks", "ssds", "security-cameras", "video-doorbells",
    ),
    "Motoring": (
        "dash-cams", "tyre-inflators", "jump-starters", "battery-chargers",
        "car-phone-mounts", "car-vacuums",
    ),
    "DIY & Garden": (
        "pressure-washers", "cordless-drills", "lawn-mowers", "hedge-trimmers",
        "leaf-blowers", "garden-tool-sets",
    ),
}
AUTHORITY_CORE_KEYS = tuple(
    dict.fromkeys(
        key
        for cluster_keys in AUTHORITY_CLUSTERS.values()
        for key in cluster_keys
    )
)


def authority_cluster_for_topic(topic_key: str) -> str:
    for name, keys in AUTHORITY_CLUSTERS.items():
        if topic_key in keys:
            return name
    return "Other"



def shopping_candidate_topics(
    available: list[tuple],
    month: int,
    limit: int = 24,
) -> list[tuple]:
    """Shortlist commercial product topics for external Google Shopping research."""
    by_key = {topic[0]: topic for topic in available}
    chosen: list[tuple] = []
    seen: set[str] = set()

    def add(key: str) -> None:
        topic = by_key.get(key)
        if topic and key not in seen and len(chosen) < limit:
            chosen.append(topic)
            seen.add(key)

    for key in SEASONAL_FALLBACKS.get(month, ()):
        add(key)
    for key in EVERGREEN_HIGH_INTENT:
        add(key)

    # Keep broad coverage after seasonal + proven commercial-intent topics.
    for topic in available:
        if len(chosen) >= limit:
            break
        if topic[0] not in seen:
            chosen.append(topic)
            seen.add(topic[0])

    return chosen


TOPICS = [
    ("air-fryers", "Air Fryers", "air fryer", 450, 500, "Home & Kitchen", "AIR FRYER GUIDE"),
    ("large-capacity-air-fryers", "Large Capacity Air Fryers", "large family air fryer", 550, 600, "Home & Kitchen", "FAMILY AIR FRYER GUIDE"),
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
    ("iphone-18-accessories", "iPhone 18 Accessories", "iPhone 18 Pro MagSafe accessories", 350, 400, "Tech", "IPHONE ACCESSORIES GUIDE"),
    ("airpods", "AirPods & Wireless Earbuds", "Apple AirPods wireless earbuds", 450, 500, "Tech", "EARBUDS BUYING GUIDE"),
    ("streaming-devices", "Streaming Devices", "Fire TV Roku streaming device", 220, 250, "Tech", "STREAMING DEVICE GUIDE"),
    ("portable-gaming-systems", "Portable Gaming Systems", "handheld gaming console", 900, 1000, "Gaming", "PORTABLE GAMING GUIDE"),
    ("loungewear", "Comfortable Loungewear", "loungewear set", 220, 250, "Home & Kitchen", "LIFESTYLE BUYING GUIDE"),
    ("beauty-sets", "Beauty & Self-Care Sets", "beauty self care set", 220, 250, "Home & Kitchen", "BEAUTY BUYING GUIDE"),
    ("seasonal-hobby-kits", "Seasonal Hobby & Craft Kits", "craft hobby kit", 220, 250, "Home & Kitchen", "HOBBY BUYING GUIDE"),
    ("garden-tool-sets", "Garden Tool Sets", "garden tool set", 300, 350, "Home & Kitchen", "GARDEN TOOL GUIDE"),
]


US_TOPIC_COPY = {
    "coffee-machines": ("Coffee Makers", "coffee maker", "COFFEE MAKER GUIDE"),
    "cordless-vacuums": ("Cordless Vacuums", "cordless vacuum", "VACUUM BUYING GUIDE"),
    "robot-vacuums": ("Robot Vacuums", "robot vacuum", "ROBOT VACUUM GUIDE"),
    "tyre-inflators": ("Tire Inflators", "tire inflator", "TIRE INFLATOR GUIDE"),
    "car-vacuums": ("Car Vacuums", "car vacuum", "CAR VACUUM GUIDE"),
    "storage-bins": ("Storage Bins & Organizers", "storage bins organizer", "HOME ORGANIZATION GUIDE"),
}

US_ENGLISH_REPLACEMENTS = (
    ("organisers", "organizers"),
    ("organiser", "organizer"),
    ("prioritise", "prioritize"),
    ("tyres", "tires"),
    ("tyre", "tire"),
    ("colour", "color"),
    ("centre", "center"),
)


def localise_topic(topic: tuple, market: str) -> tuple:
    """Use natural US product names and search terms for USA articles."""
    if market != "us":
        return topic
    key, display, query, max_uk, max_us, category, kicker = topic
    us_copy = US_TOPIC_COPY.get(key)
    if us_copy:
        display, query, kicker = us_copy
    return key, display, query, max_uk, max_us, category, kicker


def localise_template_text(value: str, market: str) -> str:
    if market != "us":
        return value
    result = value
    for british, american in US_ENGLISH_REPLACEMENTS:
        result = result.replace(british, american).replace(british.title(), american.title())
    return result

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
    # Sunday is deliberately home-only. Google demand can rank products inside
    # this pool, but it must not move the daily guide into tech, gaming or motoring.
    "storage-bins",
    "non-slip-hangers",
    "cleaning-bundles",
    "cordless-vacuums",
    "robot-vacuums",
    "steam-mops",
    "carpet-cleaners",
    "air-purifiers",
    "dehumidifiers",
    "air-fryers",
    "large-capacity-air-fryers",
    "coffee-machines",
    "slow-cookers",
    "blenders",
    "kettles",
    "microwaves",
    "stand-mixers",
    "food-processors",
    "rice-cookers",
    "multicookers",
    "juicers",
    "ice-makers",
    "bread-makers",
    "electric-blankets",
    "office-chairs",
    "loungewear",
    "beauty-sets",
    "seasonal-hobby-kits",
)


def weekend_candidate_topics(available: list[tuple], weekday: int) -> list[tuple]:
    """Restrict weekend selection before applying Google demand ranking.

    Saturday favours practical home/DIY topics. Sunday is strictly home-focused.
    If the named priority list has been exhausted for the year, Sunday falls back
    to any remaining Home & Kitchen topic before the absolute never-skip fallback.
    """
    if weekday == 5:
        priority = SATURDAY_PRIORITY
    elif weekday == 6:
        priority = SUNDAY_PRIORITY
    else:
        return available

    by_key = {topic[0]: topic for topic in available}
    focused = [by_key[key] for key in priority if key in by_key]
    if focused:
        return focused

    if weekday == 6:
        home_only = [
            topic
            for topic in available
            if len(topic) > 5 and topic[5] == "Home & Kitchen"
        ]
        if home_only:
            return home_only

    return available


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


SEO_STOPWORDS = {
    "best", "buying", "worth", "guide", "guides", "current", "compare",
    "the", "and", "for", "with", "from", "into", "your", "this", "that",
    "uk", "usa", "2026", "home", "kitchen",
}


def meaningful_tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in normalise(value).split():
            if len(token) >= 3 and token not in SEO_STOPWORDS:
                tokens.add(token)
    return tokens


def published_state_path(market: str) -> Path:
    return ROOT / "state" / (
        "articles_published.json" if market == "uk" else "articles_us_published.json"
    )


def published_article_dir(market: str) -> Path:
    return ROOT / ("articles" if market == "uk" else "articles-us")


def related_guides(
    market: str,
    current_slug: str,
    display: str,
    query: str,
    category: str,
    limit: int = 4,
) -> list[dict]:
    state = load_json(published_state_path(market))
    article_dir = published_article_dir(market)
    target_tokens = meaningful_tokens(display, query, category)
    candidates: list[tuple[int, str, dict]] = []

    for slug, entry in state.items():
        if slug == current_slug:
            continue
        if entry.get("status") != "published" or not entry.get("url"):
            continue

        title = str(entry.get("title", "")).strip()
        if not title:
            continue

        candidate_category = str(entry.get("primary_category", "")).strip()
        source_file = str(entry.get("source_file", "")).strip()
        if source_file:
            source_path = article_dir / source_file
            if source_path.exists():
                try:
                    source_article = json.loads(source_path.read_text(encoding="utf-8"))
                    candidate_category = str(
                        source_article.get("primary_category")
                        or candidate_category
                        or ""
                    ).strip()
                    title = str(source_article.get("title") or title).strip()
                except (OSError, json.JSONDecodeError):
                    pass

        score = 0
        if candidate_category and candidate_category == category:
            score += 5

        candidate_tokens = meaningful_tokens(title, candidate_category)
        score += len(target_tokens & candidate_tokens) * 2

        # Keep a few useful same-market fallbacks even when the topic overlap is
        # weak, but always rank genuinely related guides first.
        candidates.append(
            (
                score,
                title.casefold(),
                {
                    "title": title,
                    "url": str(entry["url"]),
                    "category": candidate_category,
                },
            )
        )

    candidates.sort(key=lambda row: (-row[0], row[1]))
    return [item for score, _, item in candidates if score > 0][:limit]


def _authority_page_key(cluster: str) -> str:
    return "cluster-" + cluster.casefold().replace("&", "and").replace(" ", "-")


def authority_hub_html(market: str, topic_key: str) -> str:
    cluster = authority_cluster_for_topic(topic_key)
    state_path = ROOT / "state" / (
        "site_pages_uk.json" if market == "uk" else "site_pages_us.json"
    )
    state = load_json(state_path)
    page = state.get(_authority_page_key(cluster)) or {}
    url = str(page.get("url") or "").strip()
    if not url:
        return ""
    return (
        '<p style="margin:18px 0"><strong>Explore this topic:</strong> '
        f'<a href="{html.escape(url, quote=True)}">'
        f'{html.escape(cluster)} buying guides</a></p>\n'
    )


def related_guides_html(guides: list[dict]) -> str:
    if not guides:
        return ""
    items = "\n".join(
        f'<li><a href="{html.escape(guide["url"], quote=True)}">'
        f'{html.escape(guide["title"])}</a></li>'
        for guide in guides
    )
    return (
        "<h2>Related Worth Buying guides</h2>\n"
        "<p>If you are still comparing options, these related guides may help:</p>\n"
        f"<ul>{items}</ul>\n"
    )


def quick_picks_html(items: list[dict], market: str, query: str) -> str:
    if not items:
        return ""
    if market == "us":
        return cards_html(items, retailer_urls, query)

    retailer = "eBay UK" if market == "uk" else "eBay"
    amazon = "Amazon UK" if market == "uk" else "Amazon"
    cards: list[str] = []

    for index, item in enumerate(items, start=1):
        title = " ".join(str(item.get("title", "")).split())
        price = price_text(item, market) or "Check live price"
        condition = str(item.get("condition", "")).strip() or "Check listing"
        ebay_url, amazon_url, exact_model = retailer_urls(item, market, query)
        amazon_offer = verified_amazon_offer(item, market, query)
        if amazon_offer.get("url"):
            amazon_url = str(amazon_offer["url"])

        image_url = str(((item.get("image") or {}).get("imageUrl") or "")).strip()

        seller = item.get("seller") or {}
        feedback_pct = safe_float(seller.get("feedbackPercentage"))
        seller_signal = (
            f"{feedback_pct:.1f}% positive seller feedback"
            if feedback_pct is not None
            else "Check current seller feedback"
        )

        history = item.get("_worthbuying_price_history") or {}
        history_line = ""
        if (
            safe_int(history.get("observations")) is not None
            and int(history.get("observations") or 0) >= 3
        ):
            difference = safe_float(history.get("difference_pct")) or 0.0
            if difference >= 5:
                history_line = (
                    f'<p style="margin:8px 0;color:#0b6b3a"><strong>WorthBuying price signal:</strong> '
                    f'currently about {difference:.0f}% below this listing\'s observed median '
                    f'from {int(history["observations"])} checks.</p>'
                )

        amazon_link = ""
        if amazon_offer:
            amazon_link = (
                f'<a href="{html.escape(amazon_url, quote=True)}" rel="sponsored nofollow" '
                'style="display:inline-block;padding:11px 16px;margin:0 8px 8px 0;'
                'background:#f2f4f7;color:#082f5b;text-decoration:none;border-radius:8px;font-weight:700">'
                f'Check {amazon} price</a>'
            )
        image_html = product_image_html(image_url, title) if image_url else ""
        cards.append(
            '<div style="border:1px solid #dfe6ee;border-radius:14px;padding:18px;'
            'margin:14px 0;background:#fff;">'
            f'{image_html}'
            f'<p style="margin:0 0 8px"><strong>{index}. {html.escape(title)}</strong></p>'
            f'<p style="margin:6px 0"><strong>eBay price checked:</strong> {html.escape(price)}'
            f' · {html.escape(condition)}</p>'
            f'<p style="margin:6px 0">{html.escape(seller_signal)}</p>'
            f'{history_line}'
            '<p style="margin:14px 0 2px">'
            f'<a href="{html.escape(ebay_url, quote=True)}" rel="sponsored nofollow" '
            'style="display:inline-block;padding:11px 16px;margin:0 8px 8px 0;'
            'background:#082f5b;color:#fff;text-decoration:none;border-radius:8px;font-weight:700">'
            f'Check {retailer} price</a>'
            f'{amazon_link}'
            '</p></div>'
        )

    return (
        "<h2>Best current options at a glance</h2>\n"
        + "".join(cards)
    )


def _site_page_url(market: str, key: str) -> str:
    state_path = ROOT / "state" / (
        "site_pages_uk.json" if market == "uk" else "site_pages_us.json"
    )
    state = load_json(state_path)
    return str((state.get(key) or {}).get("url") or "").strip()


def editorial_trust_html(market: str, checked_date: str) -> str:
    methodology_url = _site_page_url(market, "methodology") or (
        "https://www.worthbuyinguk.co.uk/p/how-worth-buying-chooses-products.html"
        if market == "uk"
        else "https://www.worthbuyingusa.com/p/how-worth-buying-chooses-products.html"
    )
    return (
        '<aside style="border-left:4px solid #082f5b;background:#f6f8fb;'
        'padding:16px 18px;margin:20px 0;">'
        '<p style="margin-top:0"><strong>How we choose our picks:</strong> '
        'We compare products using current pricing, specifications, customer feedback, retailer data '
        'and other relevant buying signals to help identify products we believe offer strong value. '
        'These are data-led comparisons rather than market hype. You can read more about '
        f'<a href="{html.escape(methodology_url, quote=True)}">how we choose and review products</a>.</p>'
        f'<p><small><strong>Prices checked:</strong> {html.escape(checked_date)}.</small></p>'
        '<p style="margin-bottom:0">Retailer links may be affiliate links. Recommendations are based on '
        'our published selection process, not on which retailer pays the highest commission.</p>'
        '</aside>\n'
    )


def retailer_comparison_html(market: str, topic_name: str) -> str:
    ebay = "eBay UK" if market == "uk" else "eBay"
    amazon = "Amazon UK" if market == "uk" else "Amazon"
    return (
        f"<h2>{ebay} vs {amazon}: where should you compare?</h2>\n"
        f"<p>For {html.escape(topic_name)}, it is worth checking both retailers rather than assuming one is always cheaper. "
        f"{ebay} can be useful for new, refurbished and open-box stock and exposes seller feedback clearly. "
        f"{amazon} can be useful for comparing new-stock availability, delivery options and retailer returns where offered. "
        "Always compare the exact model number, condition, warranty, delivery cost and returns policy before deciding.</p>\n"
    )


def category_faqs(topic_name: str, category: str, market: str) -> list[tuple[str, str]]:
    region = "UK" if market == "uk" else "USA"
    topic = topic_name.lower()

    common = [
        (
            f"How much should I spend on {topic}?",
            f"There is no single right budget for {topic}. Start with the features you actually need, then compare current prices for equivalent models in the {region}. Paying more only makes sense when the extra specification, warranty or build quality is useful to you.",
        ),
        (
            f"Should I buy {topic} from eBay or Amazon?",
            "Compare both for the exact same model. Check condition, seller or retailer, warranty, delivery and returns as well as the headline price. A cheaper listing is not automatically better value if the terms are weaker.",
        ),
    ]

    if category == "Tech":
        common.extend([
            (
                f"What should I check before buying {topic}?",
                "Confirm the exact model number or generation, compatibility, ports or connectivity, included accessories and warranty. For refurbished or open-box products, read the condition description carefully.",
            ),
            (
                f"Is refurbished {topic} worth considering?",
                "It can be, particularly when the seller has strong feedback and the listing clearly explains condition, battery or cosmetic wear where relevant, warranty and returns. Compare the saving against a new equivalent before buying.",
            ),
        ])
    elif category == "Motoring":
        common.extend([
            (
                f"How do I know whether {topic} will fit my car?",
                "Check the vehicle compatibility or fitment information on the live listing and confirm dimensions, connectors and included adapters. Do not rely on a generic product title alone.",
            ),
            (
                f"What matters most when comparing {topic}?",
                "Compatibility, clear specifications, seller reputation, warranty, included accessories and returns matter more than a large claimed discount.",
            ),
        ])
    elif category == "Gaming":
        common.extend([
            (
                f"How do I choose compatible {topic}?",
                "Check the exact console, PC or handheld platform supported, connection type, included cables or adapters and whether any features depend on proprietary software.",
            ),
            (
                f"Are cheaper {topic} good value?",
                "Sometimes, but compare build quality, compatibility, warranty and included accessories. A lower price can be good value when it still meets the features you need.",
            ),
        ])
    else:
        common.extend([
            (
                f"What should I look for when choosing {topic}?",
                "Check dimensions, capacity or coverage, power use where relevant, cleaning or maintenance requirements, warranty and replacement parts or consumables. The most useful features depend on how often and where you will use the product.",
            ),
            (
                f"Is it worth paying more for {topic}?",
                "Only when the extra capacity, convenience, durability or warranty is useful for your needs. Compare like-for-like models and avoid paying for features you are unlikely to use.",
            ),
        ])

    return common[:4]


def faq_html(topic_name: str, category: str, market: str) -> str:
    blocks = []
    for question, answer in category_faqs(topic_name, category, market):
        blocks.append(
            f"<h3>{html.escape(question)}</h3>\n"
            f"<p>{html.escape(answer)}</p>"
        )
    return "<h2>Frequently asked questions</h2>\n" + "\n".join(blocks) + "\n"


def buyer_intro(display: str, region: str, year: int, live: bool) -> str:
    topic = display.lower()
    if live:
        return (
            f"Shopping for {topic} in the {region}? We have narrowed the current market to a practical "
            "shortlist worth comparing, focusing on useful features, realistic prices and seller quality "
            "so you can get to the strongest options faster."
        )
    return (
        f"Shopping for {topic} in the {region}? This guide focuses on the features and buying checks that "
        "matter most, with live retailer searches so you can compare current stock and prices before deciding."
    )


def seo_description(display: str, region: str, year: int) -> str:
    return (
        f"Compare {display.lower()} in the {region} for {year}, with current marketplace picks, "
        "buying advice, retailer comparison, FAQs and related Worth Buying guides."
    )


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


def topic_already_covered(article_dir: Path, topic: tuple, year: int) -> bool:
    key, display = topic[0], topic[1]
    wanted = normalise(display)
    for path in article_dir.glob("*.json"):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        generator_topic = normalise(str((article.get("_generator") or {}).get("topic", "")))
        title = str(article.get("title", ""))
        slug = str(article.get("slug", path.stem))
        source_sha = str(article.get("source_sha", ""))
        same_year = str(year) in title or str(year) in slug or str(year) in source_sha
        if same_year and generator_topic and generator_topic == normalise(key):
            return True

        if str(year) in title and wanted and wanted in normalise(title):
            return True
    return False


def _article_generated_date(article: dict) -> date | None:
    seo_date = str((article.get("_seo") or {}).get("last_checked_iso") or "").strip()
    source_sha = str(article.get("source_sha") or "").strip()
    candidate = seo_date[:10] or source_sha[:10]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def topic_last_generated_date(
    article_dir: Path,
    topic: tuple,
    year: int,
) -> date | None:
    topic_key = normalise(topic[0])
    latest: date | None = None
    for path in article_dir.glob("*.json"):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        generator_topic = normalise(str((article.get("_generator") or {}).get("topic", "")))
        if generator_topic != topic_key:
            continue
        generated = _article_generated_date(article)
        if generated is None or generated.year != year:
            continue
        if latest is None or generated > latest:
            latest = generated
    return latest


def authority_candidate_pool(
    article_dir: Path,
    year: int,
    weekday: int,
) -> list[tuple]:
    core = [topic for topic in TOPICS if topic[0] in AUTHORITY_CORE_KEYS]
    focused = weekend_candidate_topics(core, weekday)
    today = datetime.now(LONDON_TZ).date()

    # A daily slot can be either a new authority article or a commercially
    # useful refresh. Refreshed guides are promoted as today's feature and
    # moved back to the top of Blogger without creating a duplicate URL.
    due: list[tuple] = []
    dated: list[tuple[date, tuple]] = []
    for topic in focused:
        last = topic_last_generated_date(article_dir, topic, year)
        if last is None:
            due.append(topic)
            continue
        dated.append((last, topic))
        if (today - last).days >= REFRESH_AFTER_DAYS:
            due.append(topic)

    if due:
        return due

    dated.sort(key=lambda row: row[0])
    return [topic for _, topic in dated[:12]] or focused


def _fallback_topic(
    available: list[tuple],
    month: int,
) -> tuple:
    by_key = {topic[0]: topic for topic in available}

    for key in SEASONAL_FALLBACKS.get(month, ()):
        topic = by_key.get(key)
        if topic:
            return topic

    for key in EVERGREEN_HIGH_INTENT:
        topic = by_key.get(key)
        if topic:
            return topic

    # Absolute last resort: publish the next available curated product topic.
    # This keeps the daily cadence intact even when stronger seasonal options
    # have already been covered.
    return available[0]


def pick_topic(
    article_dir: Path,
    year: int,
    weekday: int,
    market: str,
    month: int | None = None,
) -> tuple[tuple, dict | None, dict | None, float | None]:
    available = authority_candidate_pool(article_dir, year, weekday)
    if not available:
        raise RuntimeError("No authority-cluster topics are available for publication.")

    if month is None:
        month = datetime.now(LONDON_TZ).month

    candidate_pool = available
    if weekday == 5:
        print(
            f"[weekend-focus] {market.upper()}: Saturday home/DIY pool "
            f"({len(candidate_pool)} available topic(s))"
        )
    elif weekday == 6:
        print(
            f"[weekend-focus] {market.upper()}: Sunday home-only pool "
            f"({len(candidate_pool)} available topic(s))"
        )

    # Primary signal: external Google Shopping search interest in GB/US.
    # This measures what people are searching for on Google Shopping and does
    # not use WorthBuying Search Console or any traffic from our own sites.
    shopping_candidates = shopping_candidate_topics(candidate_pool, month)
    shopping_ranked = rank_topics_by_google_shopping(
        shopping_candidates,
        market,
    )
    if shopping_ranked:
        topic, shopping_signal = shopping_ranked[0]
        print(
            f"[google-shopping-pick] {market.upper()}: {topic[1]} "
            f"(query='{shopping_signal.get('query')}', "
            f"score={float(shopping_signal.get('score') or 0):.2f}, "
            f"current={float(shopping_signal.get('shopping_current') or 0):.2f}, "
            f"momentum={float(shopping_signal.get('shopping_momentum') or 0):.3f}, "
            f"vs_air_fryer={float(shopping_signal.get('shopping_relative_to_anchor') or 0):.3f})"
        )
        return (
            topic,
            shopping_signal,
            None,
            float(shopping_signal.get("score") or 0),
        )

    # Secondary external signal: Google's Trending Now feed. This is broader
    # than shopping intent and is often news/sport-led, so it is used only if
    # the Shopping comparison endpoint is unavailable or returns no product data.
    trend_ranked = rank_topics_by_trends(candidate_pool, market)
    if trend_ranked:
        topic, trend_signal = trend_ranked[0]
        trend_score = float(trend_signal.get("score") or 0)
        print(
            f"[google-web-trend-pick] {market.upper()}: {topic[1]} matched "
            f"'{trend_signal.get('query')}' "
            f"(score={trend_score:.2f}, "
            f"traffic={trend_signal.get('traffic_label') or trend_signal.get('traffic')})"
        )
        return topic, trend_signal, None, trend_score

    # Never skip a day. If Google cannot provide a usable live product signal,
    # use a seasonal commercial-intent fallback, then evergreen high-intent.
    topic = _fallback_topic(candidate_pool, month)
    print(
        f"[seasonal-fallback-pick] {market.upper()}: {topic[1]} "
        f"(month={month}; external Google Shopping/Trends data unavailable today)"
    )
    return topic, None, None, None


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


def _implausible_marketplace_title(title: str) -> bool:
    value = " ".join(str(title).split())
    lowered = value.casefold()

    # Common low-quality/spam patterns that can surface in broad marketplace
    # searches and are poor products for an editorial recommendation.
    blocked_phrases = (
        "mystery box",
        "empty box",
        "box only",
        "manual only",
        "for parts",
        "not working",
        "spares repair",
        "read description",
    )
    if any(term in lowered for term in blocked_phrases):
        return True

    # Reject physically implausible battery-capacity claims such as
    # "9000000mAh power bank", which are a strong trust warning.
    for match in re.finditer(r"\b(\d{6,})\s*mah\b", lowered):
        try:
            if int(match.group(1)) > 200_000:
                return True
        except ValueError:
            pass

    # Excessively promotional titles are a weak editorial signal.
    promo_tokens = re.findall(r"\b(?:hot|wow|sale|cheap|bargain)\b", lowered)
    return len(promo_tokens) >= 3


def _query_relevant(title: str, query: str) -> bool:
    query_tokens = meaningful_tokens(query)
    if not query_tokens:
        return True
    title_tokens = meaningful_tokens(title)
    return bool(query_tokens & title_tokens)


def _has_product_image(item: dict) -> bool:
    return bool(str(((item.get("image") or {}).get("imageUrl") or "")).strip())


def listing_score(
    item: dict,
    max_price: float,
    expected_currency: str,
    query: str = "",
) -> float | None:
    title_raw = " ".join(str(item.get("title", "")).split())
    title = title_raw.casefold()
    condition = str(item.get("condition", "")).casefold()
    if "refurbished" in query.casefold() and "refurbished" not in condition:
        return None

    if _implausible_marketplace_title(title_raw):
        return None
    if query and not _query_relevant(title_raw, query):
        return None
    if expected_currency == "USD" and not relevant_product(title_raw, query):
        return None
    if not _has_product_image(item):
        return None

    price = safe_float((item.get("price") or {}).get("value"))
    currency = str((item.get("price") or {}).get("currency", ""))
    minimum_price = max(8.0, max_price * 0.05)
    if (
        price is None
        or price < minimum_price
        or price > max_price
        or currency != expected_currency
    ):
        return None

    buying_options = item.get("buyingOptions") or []
    if buying_options and "FIXED_PRICE" not in buying_options:
        return None

    seller = item.get("seller") or {}
    feedback_pct = safe_float(seller.get("feedbackPercentage"))
    feedback_count = safe_int(seller.get("feedbackScore"))

    if feedback_pct is not None and feedback_pct < 98.0:
        return None
    if feedback_count is not None and feedback_count < 100:
        return None

    score = 45.0

    if feedback_pct is not None:
        if feedback_pct >= 99.5:
            score += 16
        elif feedback_pct >= 99.0:
            score += 13
        else:
            score += 8

    if feedback_count is not None:
        if feedback_count >= 10_000:
            score += 8
        elif feedback_count >= 1_000:
            score += 6
        elif feedback_count >= 250:
            score += 4
        else:
            score += 2

    marketing = item.get("marketingPrice") or {}
    discount = safe_float(marketing.get("discountPercentage"))
    if discount and discount > 0:
        score += min(discount, 15)

    ratio = price / max_price if max_price else 1
    if 0.10 <= ratio <= 0.60:
        score += 7
    elif ratio <= 0.80:
        score += 4

    condition = str(item.get("condition", "")).casefold()
    if "new" in condition:
        score += 3
    elif any(term in condition for term in ("refurbished", "open box")):
        score += 2

    # Brand/model-like identifiers make exact cross-retailer comparison more
    # useful and more commercially valuable than generic marketplace titles.
    _, exact_model = amazon_model_query(title_raw, query or title_raw)
    if exact_model:
        score += 6

    return round(score, 2)


def _record_price_history(items: list[dict], market: str, article_slug: str) -> None:
    state = load_json(PRICE_HISTORY_PATH)
    now = datetime.now(LONDON_TZ)
    today = now.date().isoformat()

    for item in items:
        item_id = str(item.get("itemId") or "").strip()
        price = safe_float((item.get("price") or {}).get("value"))
        currency = str((item.get("price") or {}).get("currency") or "").strip()
        if not item_id or price is None or not currency:
            continue

        key = f"daily|{market}|{item_id}"
        entry = state.setdefault(
            key,
            {"title": str(item.get("title") or ""), "observations": []},
        )
        entry["title"] = str(item.get("title") or entry.get("title") or "")
        entry["article_slug"] = article_slug
        entry["tracking_status"] = "active"
        entry["last_attempt_date"] = today
        observations = entry.setdefault("observations", [])

        # One observation per listing/day is enough for editorial price history
        # and prevents retry runs from bloating the file.
        observations = [
            obs for obs in observations
            if str(obs.get("date") or "") != today
        ]
        observations.append(
            {
                "date": today,
                "ts": now.isoformat(),
                "price": price,
                "currency": currency,
            }
        )
        observations = observations[-90:]
        entry["observations"] = observations

        historic = [
            safe_float(obs.get("price"))
            for obs in observations
            if safe_float(obs.get("price")) is not None
        ]
        if len(historic) >= 3:
            typical = float(median(historic))
            difference = ((typical - price) / typical * 100) if typical > 0 else 0.0
            item["_worthbuying_price_history"] = {
                "observations": len(historic),
                "median": round(typical, 2),
                "difference_pct": round(difference, 1),
                "currency": currency,
            }

    save_json(PRICE_HISTORY_PATH, state)


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
        score = listing_score(item, max_price, expected_currency, query=query)
        if score is None:
            continue

        fingerprint = " ".join(normalise(str(item.get("title", ""))).split()[:8])
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        enriched = dict(item)
        enriched["_worthbuying_score"] = score
        scored.append((score, enriched))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    shortlist = [item for _, item in scored[:8]]
    if market == "us":
        from src.product_image_quality import checked_product_image
        import requests
        verified = []
        for summary in shortlist:
            item_id = str(summary.get("itemId") or "")
            if not item_id:
                continue
            try:
                item = client.get_item(item_id, affiliate_reference=f"daily-{slug}")
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (404, 410):
                    continue
                raise
            if item.get("itemId") != item_id or not live_listing(item, datetime.now(timezone.utc)):
                continue
            score = listing_score(item, max_price, expected_currency, query=query)
            if score is None:
                continue
            try:
                image, _, _ = checked_product_image(item["image"]["imageUrl"])
            except (KeyError, RuntimeError):
                continue
            item["image"]["imageUrl"] = image
            item["_worthbuying_score"] = score
            verified.append(item)
        shortlist = verified
    _record_price_history(shortlist, market, slug)
    return shortlist[:4]


def amazon_model_query(title: str, fallback_query: str) -> tuple[str, bool]:
    """Build a tighter Amazon search using brand + model number when available."""

    clean = " ".join(title.split())
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*", clean)

    model = ""
    for token in tokens:
        # Basket capacities and feature counts are specifications, not models.
        if re.fullmatch(
            r"(?:\d+(?:\.\d+)?x)?\d+(?:\.\d+)?(?:ml|l|w|v|db|hz|mah|gb|tb|inch|cm|mm)"
            r"|\d+[-/]?in[-/]?\d+",
            token, re.I,
        ):
            continue
        compact = re.sub(r"[^A-Za-z0-9]", "", token)
        if len(compact) < 5:
            continue
        if len(re.findall(r"[A-Za-z]", compact)) < 2:
            continue
        if len(re.findall(r"\d", compact)) < 2:
            continue

        lower = compact.casefold()
        # Skip capacity / electrical / dimension-style tokens rather than
        # mistaking them for a manufacturer model number.
        if re.fullmatch(r"\d+(?:ml|l|w|v|db|hz|mah|gb|tb|inch|cm|mm)", lower):
            continue
        if re.fullmatch(r"\d+(?:pint|pin|sqft)", lower):
            continue

        model = compact
        break

    if model:
        brand = tokens[0] if tokens else ""
        if brand and brand.casefold() not in {
            "the", "new", "best", "refurbished", "certified", "portable",
            "electric", "dehumidifier", "vacuum", "cleaner",
        }:
            return f"{brand} {model}", True
        return model, True

    # No reliable model number: use a concise version of the listing title.
    # This is still narrower than a category-only search.
    words = clean.split()
    concise = " ".join(words[:10]).strip()
    return (concise or fallback_query), False


def retailer_urls(item: dict, market: str, fallback_query: str) -> tuple[str, str, bool]:
    title = " ".join(str(item.get("title", "")).split())
    amazon_query, exact_model_search = amazon_model_query(title, fallback_query)

    ebay_url = str((item.get("itemWebUrl") if market == "us" else item.get("itemAffiliateWebUrl"))
                   or item.get("itemWebUrl") or "").strip()
    if not ebay_url:
        base = "https://www.ebay.co.uk/sch/i.html" if market == "uk" else "https://www.ebay.com/sch/i.html"
        ebay_url = f"{base}?_nkw={quote_plus(fallback_query)}&_sop=15"

    amazon_base = "https://www.amazon.co.uk/s" if market == "uk" else "https://www.amazon.com/s"
    amazon_url = f"{amazon_base}?k={quote_plus(amazon_query)}"
    return ebay_url, amazon_url, exact_model_search


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


def money_text(price: float, currency: str) -> str:
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, f"{currency} ")
    return f"{symbol}{price:,.2f}"


def _model_token(title: str, fallback_query: str) -> str:
    query, exact = amazon_model_query(title, fallback_query)
    if not exact:
        return ""
    tokens = query.split()
    return re.sub(r"[^A-Za-z0-9]", "", tokens[-1]).casefold()


def verified_amazon_offer(item: dict, market: str, fallback_query: str) -> dict:
    """Expose only a direct retailer offer matching the listing's brand and model."""
    offer = item.get("_amazon_offer") or {}
    title = str(item.get("title") or "")
    model = _model_token(title, fallback_query)
    words = title.split()
    brand = str(item.get("brand") or (words[0] if words else "")).strip().casefold()
    if not model or not brand or not brand.isalpha() or brand in {
        "new", "best", "refurbished", "certified", "portable", "electric",
        "dehumidifier", "vacuum", "cleaner", "large", "family", "double",
    }:
        return {}
    offer_title = str(offer.get("title") or "").casefold()
    offer_tokens = {
        re.sub(r"[^a-z0-9]", "", token)
        for token in re.findall(r"[a-z0-9][a-z0-9._/-]*", offer_title)
    }
    if (model not in offer_tokens
            or not re.search(r"\b" + re.escape(brand) + r"\b", offer_title)
            or not relevant_product(offer_title, fallback_query)):
        return {}
    try:
        parts = urlsplit(str(offer.get("url") or ""))
        price = float(offer.get("price") or 0)
        host = "amazon.co.uk" if market == "uk" else "amazon.com"
        currency = "GBP" if market == "uk" else "USD"
        if (parts.scheme != "https" or parts.hostname not in {host, "www." + host}
                or parts.username or parts.password or parts.port not in {None, 443}
                or not re.match(r"^/(?:dp|gp/product)/[A-Z0-9]{10}(?:/|$)", parts.path, re.I)
                or offer.get("currency") != currency or not math.isfinite(price) or price <= 0):
            return {}
    except (TypeError, ValueError):
        return {}
    return offer


def add_amazon_prices(items: list[dict], market: str, fallback_query: str) -> None:
    """Attach a verified Amazon offer when Creators API access is configured."""
    client = AmazonCreatorsClient.from_env(market)
    if client is None:
        print(f"[amazon-skip] {market.upper()} Creators API credentials are not configured")
        return

    for item in items:
        item.pop("_amazon_offer", None)
        title = " ".join(str(item.get("title", "")).split())
        search_query, exact_model_search = amazon_model_query(title, fallback_query)
        model = _model_token(title, fallback_query)
        try:
            offers = client.search_offers(search_query)
        except Exception as exc:
            print(
                f"[amazon-warning] {market.upper()} price lookup failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        for offer in offers:
            normal_title = re.sub(r"[^a-z0-9]", "", offer.title.casefold())
            if exact_model_search and model and model not in normal_title:
                continue
            if not exact_model_search:
                # A category or generic search is not sufficient evidence that the
                # Amazon result is the same product as the eBay listing.
                continue
            if market == "us":
                brand = str(item.get("brand") or "").strip().casefold()
                if not brand or brand not in offer.title.casefold() or not amazon_direct({
                    "price": offer.price, "currency": offer.currency, "url": offer.url,
                }):
                    continue
            candidate = {
                "title": offer.title,
                "price": offer.price,
                "currency": offer.currency,
                "url": offer.url,
            }
            if verified_amazon_offer({**item, "_amazon_offer": candidate}, market, fallback_query):
                item["_amazon_offer"] = candidate
                break


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
        condition = str(item.get("condition", "")).strip()
        condition_text = (
            f" <strong>Condition shown:</strong> {html.escape(condition)}."
            if condition else ""
        )
        ebay_url, amazon_url, exact_model_search = retailer_urls(item, market, query)
        amazon_offer = (verified_amazon_offer(item, market, query) if market == "uk"
                        else item.get("_amazon_offer") or {})
        if market == "us" and not amazon_direct(amazon_offer):
            amazon_offer = {}
        if amazon_offer.get("url"):
            amazon_url = str(amazon_offer["url"])
        price_parts = [f"eBay {price}" if price else "eBay: check the live listing"]
        if amazon_offer.get("price") and amazon_offer.get("currency"):
            price_parts.append(
                "Amazon "
                + money_text(float(amazon_offer["price"]), str(amazon_offer["currency"]))
            )
        prices = "; ".join(price_parts)
        amazon_link_label = (
            f"Search {amazon} for this model"
            if exact_model_search
            else f"Search {amazon} for this product"
        )
        if amazon_offer and (market != "us" or amazon_direct(amazon_offer)):
            amazon_link_label = f"Check this model on {amazon}"
        ebay_attrs = (' data-wb-retailer="ebay" data-wb-placement="detail"' if market == "us" else "")
        amazon_attrs = (' data-wb-retailer="amazon" data-wb-placement="'
                        + ('detail' if amazon_direct(amazon_offer) else 'search-alternative') + '"'
                        if market == "us" else "")
        amazon_link = ""
        if amazon_offer or market == "us":
            amazon_link = (
                f'<a href="{html.escape(amazon_url, quote=True)}" rel="sponsored nofollow"{amazon_attrs}>'
                f"{amazon_link_label}</a>"
            )

        parts.append(
            f"<h3>{index}. {safe_title}</h3>\n"
            f"<p><strong>Prices when checked:</strong> {html.escape(prices)}."
            f"{condition_text} This listing made the shortlist because it passed our automated price, "
            f"fixed-price and seller-quality checks for {html.escape(topic_name)}."
            f"{html.escape(discount_text(item))}</p>\n"
            f"<p>{html.escape(seller_text(item))} Availability, condition and price can change quickly, "
            "so verify the exact model, specification, warranty, delivery and returns on the retailer page.</p>\n"
            + (
                f"<p><strong>WorthBuying price history:</strong> this listing is currently about "
                f"{float((item.get('_worthbuying_price_history') or {}).get('difference_pct') or 0):.0f}% below "
                f"its observed median across "
                f"{int((item.get('_worthbuying_price_history') or {}).get('observations') or 0)} checks.</p>\n"
                if int((item.get('_worthbuying_price_history') or {}).get('observations') or 0) >= 3
                and float((item.get('_worthbuying_price_history') or {}).get('difference_pct') or 0) >= 5
                else ""
            )
            + f'<p><a href="{html.escape(ebay_url, quote=True)}" rel="sponsored nofollow"{ebay_attrs}>'
            f"View on {retailer}</a>\n"
            f"{amazon_link}</p>\n"
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
            f"<h3>{index}. {html.escape(heading)}</h3>\n"
            f"<p>Compare current {html.escape(topic_name)} listings in this part of the market. "
            "The live retailer pages are the best place to check current models, prices, seller details "
            "and availability.</p>\n"
            f'<p><a href="{html.escape(ebay_url, quote=True)}" rel="sponsored nofollow">'
            f"Compare on {retailer}</a>\n"
            f'<a href="{html.escape(amazon_url, quote=True)}" rel="sponsored nofollow">'
            f"Compare on {amazon}</a></p>\n"
        )
    return "\n".join(parts)


def evergreen_article_slug(topic_key: str, market: str) -> str:
    """Reuse the permanent buying-guide slug, never a temporary retailer roundup."""
    article_dir = published_article_dir(market)
    wanted = normalise(topic_key)
    candidates: list[tuple[int, str]] = []

    for path in article_dir.glob("*.json"):
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        generator = article.get("_generator") or {}
        if normalise(str(generator.get("topic") or "")) != wanted:
            continue

        # Supporting pages and retailer-specific roundups are separate assets.
        # They must never become the canonical evergreen URL for a daily guide.
        if str(generator.get("content_type") or "") == "authority-support":
            continue
        if str(generator.get("channel") or "").casefold() == "rakuten":
            continue

        slug = str(article.get("slug") or path.stem).strip()
        if not slug or slug.startswith("approved-retailer-"):
            continue

        expected_prefix = f"best-{topic_key}-worth-buying-{market}"
        priority = 0 if slug.startswith(expected_prefix) else 1
        candidates.append((priority, slug))

    if candidates:
        candidates.sort(key=lambda row: (row[0], row[1]))
        return candidates[0][1]

    # Early manually published guides predate _generator metadata. Their exact
    # topic-shaped filenames still identify the existing permanent article.
    for path in sorted(article_dir.glob(f"best-{topic_key}-worth-buying-{market}-*.json"), reverse=True):
        article = load_json(path)
        if not article.get("_generator") and article.get("slug") == path.stem:
            return path.stem

    return f"best-{topic_key}-worth-buying-{market}"


def build_article(
    topic: tuple,
    market: str,
    year: int,
    trend_signal: dict | None = None,
    gsc_signal: dict | None = None,
    demand_score: float | None = None,
) -> dict:
    topic = localise_topic(topic, market)
    key, display, query, max_uk, max_us, category, kicker = topic
    region = "UK" if market == "uk" else "USA"
    directory_name = "articles" if market == "uk" else "articles-us"
    max_price = float(max_uk if market == "uk" else max_us)
    slug = evergreen_article_slug(key, market)

    try:
        picks = current_picks(market, query, max_price, slug)
    except Exception as exc:
        print(f"[daily-warning] {market.upper()} eBay lookup failed for {display}: {type(exc).__name__}: {exc}")
        picks = []

    if picks:
        add_amazon_prices(picks, market, query)

    live = len(picks) >= 3
    sections = (
        live_sections(picks, market, display, query)
        if live
        else fallback_sections(market, display, query)
    )

    checks = [
        localise_template_text(check, market)
        for check in CATEGORY_CHECKS.get(category, CATEGORY_CHECKS["Home & Kitchen"])
    ]
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)
    guides = related_guides(
        market=market,
        current_slug=slug,
        display=display,
        query=query,
        category=category,
        limit=4,
    )

    trend_title_phrase = trend_keyword_for_title(topic, trend_signal)
    title_subject = trend_title_phrase or display
    title = f"Best {title_subject} Worth Buying in the {region} ({year})"
    source_sha = f"{datetime.now(LONDON_TZ).date().isoformat()}-{key}-{market}-daily-v6"
    primary_keyword = f"best {title_subject.lower()} {region.lower()} {year}"
    secondary_keywords = [
        f"{display.lower()} buying guide {region.lower()}",
        f"{display.lower()} worth buying {year}",
        f"compare {display.lower()} {region.lower()}",
    ]
    if trend_signal and trend_signal.get("query"):
        trend_query = " ".join(str(trend_signal["query"]).split())
        secondary_keywords.insert(0, trend_query)
    description = seo_description(display, region, year)
    checked_at = datetime.now(LONDON_TZ)
    checked_date = (
        checked_at.strftime("%d %B %Y").lstrip("0")
        if market == "uk"
        else f"{checked_at.strftime('%B')} {checked_at.day}, {checked_at.year}"
    )

    methodology = (
        f"For this guide, our automation searched current {('eBay UK' if market == 'uk' else 'eBay')} "
        f"listings for {html.escape(display)} and applied basic fixed-price, price-ceiling and seller-feedback checks. "
        "These are current marketplace picks rather than hands-on laboratory test results."
        if live
        else
        f"Our live marketplace lookup did not return enough listings that passed the automated filters today, "
        f"so this guide links to current retailer searches for {html.escape(display)} instead of inventing product recommendations."
    )

    content = (
        f"<p><strong>{html.escape(buyer_intro(display, region, year, live))}</strong></p>\n"
        + (quick_picks_html(picks, market, query) if live and market == "us" else "")
        +
        f"<p>{methodology} Prices and availability can change after publication, so always verify the live listing.</p>\n"
        f"{editorial_trust_html(market, checked_date)}"
        f"{quick_picks_html(picks, market, query) if live and market != 'us' else ''}"
        f"<h2>{'Current picks worth comparing' if live else 'Current retailer searches worth checking'}</h2>\n"
        f"{sections}\n"
        "<h2>How to choose the right option</h2>\n"
        f"<p>The best {html.escape(display.lower())} for you depends on your budget, how often you will use it "
        "and which features genuinely matter. Use the checks below to compare equivalent models rather than choosing "
        "only on headline price or a claimed discount.</p>\n"
        f"<ul>{check_html}</ul>\n"
        f"{retailer_comparison_html(market, display)}"
        "<h2>How we choose these daily picks</h2>\n"
        "<p>Our product comparisons are built using current retailer data, market analysis and available marketplace feedback "
        "to identify the products most worthy of consideration. We do not rely on promotional messaging, manufacturer claims "
        "or advertised discounts when making recommendations. Instead, we focus on products that demonstrate strong value, "
        "positive seller signals and a credible marketplace track record. Although we have not physically tested every item "
        "featured, our methodology is designed to help consumers make informed and confident purchasing decisions. Where "
        "performance, safety or durability are especially important, we also encourage checking independent reviews of the "
        "exact model.</p>\n"
        f"{faq_html(display, category, market)}"
        f"{authority_hub_html(market, key)}"
        f"{related_guides_html(guides)}"
        "<p><em>Prices, promotions, seller feedback and availability change regularly. Always check the live retailer page "
        "before purchasing.</em></p>"
    )
    if market == "us":
        measurement = str(load_json(ROOT / "automation" / "usa_conversion_pilot.json").get("ga4_measurement_id") or "")
        content = (f'<div data-wb-article="{html.escape(slug, quote=True)}" '
                   f'data-wb-experiment="{EXPERIMENT}">{content}</div>'
                   + tracking_script(slug, measurement))

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
            "Read the guide 🔗 {url}\n"
            "#BuyingGuide #WorthBuying"
        ),
        "content_html": content,
        "_seo": {
            "version": "daily-seo-v7-authority-revenue",
            "target_country": "GB" if market == "uk" else "US",
            "language": "en-GB" if market == "uk" else "en-US",
            "primary_keyword": primary_keyword,
            "secondary_keywords": secondary_keywords,
            "description": description,
            "search_intent": "commercial investigation",
            "related_guide_count": len(guides),
            "google_demand_signal": trend_signal,
            "google_demand_title_phrase": trend_title_phrase,
            "demand_score": demand_score,
            "last_checked_iso": checked_at.date().isoformat(),
            "evergreen_refresh": True,
            "stable_slug": True,
            "authority_cluster": authority_cluster_for_topic(key),
            "editorial_method": "retailer-data-plus-quality-filters",
        },
        "_monetisation": {
            "version": EXPERIMENT if market == "us" else "affiliate-conversion-v2",
            "primary_goal": "qualified-affiliate-click",
            "networks": ["eBay", "Amazon"],
            "commercial_intent": "high",
            "retailer_cta_count": len(picks) * 2 if live else 8,
            "authority_cluster": authority_cluster_for_topic(key),
        },
        "_promotion": {
            "daily_featured_date": checked_at.date().isoformat(),
            "promotion_token": f"{checked_at.date().isoformat()}:{market}:{slug}",
            "return_to_top": True,
            "is_refresh": False,
        },
        "_generator": {
            "market": market,
            "topic": key,
            "live_ebay_picks": live,
            "pick_count": len(picks),
            "article_directory": directory_name,
        },
        "youtube_short_points": [
            " — ".join(
                part
                for part in (
                    str(item.get("condition") or "Current listing").strip(),
                    f"eBay {price_text(item, market)}" if price_text(item, market) else "",
                    (
                        "Amazon "
                        + money_text(
                            float((item.get("_amazon_offer") or {})["price"]),
                            str((item.get("_amazon_offer") or {})["currency"]),
                        )
                        if (item.get("_amazon_offer") or {}).get("price")
                        and (item.get("_amazon_offer") or {}).get("currency")
                        else ""
                    ),
                )
                if part
            )
            for item in picks[:3]
        ],
    }


def main() -> None:
    now = datetime.now(LONDON_TZ)
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

        refresh_tracked_prices(PRICE_HISTORY_PATH, market, EbayClient.for_market(market))

        article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
        article_dir.mkdir(parents=True, exist_ok=True)

        topic, trend_signal, gsc_signal, demand_score = pick_topic(
            article_dir, year, weekday, market, month=now.month
        )

        article = build_article(
            topic,
            market,
            year,
            trend_signal=trend_signal,
            gsc_signal=gsc_signal,
            demand_score=demand_score,
        )
        target = article_dir / f"{article['slug']}.json"
        refreshing = target.exists()
        article.setdefault("_promotion", {})["is_refresh"] = refreshing
        article["_promotion"]["promotion_token"] = f"{today}:{market}:{article['slug']}"

        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state[market] = {
            "date": today,
            "slug": article["slug"],
            "title": article["title"],
            "topic": topic[0],
            "demand_score": demand_score,
            "google_query": (trend_signal or {}).get("query"),
            "google_score": (trend_signal or {}).get("score"),
            "google_source": (trend_signal or {}).get("source"),
            "google_cached": bool((trend_signal or {}).get("cached")),
            "google_observed_at": (trend_signal or {}).get("observed_at"),
            "shopping_current": (trend_signal or {}).get("shopping_current"),
            "shopping_momentum": (trend_signal or {}).get("shopping_momentum"),
            "shopping_relative_to_anchor": (trend_signal or {}).get("shopping_relative_to_anchor"),
            "trend_traffic": (trend_signal or {}).get("traffic"),
            "day": day_name,
            "weekend_priority": is_weekend,
            "weekend_focus": (
                "sunday-home"
                if weekday == 6
                else "saturday-home-diy"
                if weekday == 5
                else None
            ),
            "selection_basis": (
                "google-shopping-trends-cache"
                if (trend_signal or {}).get("cached")
                else "google-shopping-trends"
                if (trend_signal or {}).get("source") == "google-trends-google-shopping"
                else "google-trending-now"
                if trend_signal
                else "seasonal-commercial-fallback"
            ),
            "live_ebay_picks": bool(article["_generator"]["live_ebay_picks"]),
            "pick_count": int(article["_generator"]["pick_count"]),
            "content_action": "refreshed" if refreshing else "created",
            "authority_cluster": article["_seo"]["authority_cluster"],
            "monetisation_goal": article["_monetisation"]["primary_goal"],
        }
        generated += 1
        action = "refreshed" if refreshing else "created"
        print(
            f"[daily-{action}] {market.upper()}: {target.relative_to(ROOT)} "
            f"(day={day_name}, selection_basis={state[market]['selection_basis']}, "
            f"live eBay picks={article['_generator']['pick_count']})"
        )

    save_json(STATE_PATH, state)
    print(f"Daily article generation complete: {generated} article(s) created.")


if __name__ == "__main__":
    main()


