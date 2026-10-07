from __future__ import annotations

import argparse
import html
import json
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import generate_daily_articles as daily
from src.amazon_creators import AmazonCreatorsClient
from src.product_image_quality import product_image_html


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "prime_big_deal_days.json"
LONDON = ZoneInfo("Europe/London")
EVENT_START = date(2026, 10, 6)
EVENT_END = date(2026, 10, 7)
CLEANUP_DATE = date(2026, 10, 8)
TARGET_PER_MARKET_PER_DAY = 3
EVENT_KEY = "prime-big-deal-days-2026"
EVENT_NAME = "Prime Big Deal Days"

# Ordered by commercial intent. Each scheduled run publishes at most one guide
# per market, so prices are rechecked across the day rather than all at once.
DAY_PLANS = {
    date(2026, 10, 6): (
        "large-capacity-air-fryers",
        "robot-vacuums",
        "wireless-earbuds",
        "power-banks",
        "smartwatches",
        "coffee-machines",
        "tvs",
    ),
    date(2026, 10, 7): (
        "tvs",
        "coffee-machines",
        "ssds",
        "air-fryers",
        "tablets",
        "soundbars",
        "security-cameras",
    ),
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


def event_active(run_date: date) -> bool:
    return EVENT_START <= run_date <= EVENT_END


def display_date(run_date: date) -> str:
    return f"{run_date.day} {run_date.strftime('%B %Y')}"


def topic_by_key(key: str) -> tuple:
    return next(topic for topic in daily.TOPICS if topic[0] == key)


def article_dir(market: str) -> Path:
    return ROOT / ("articles" if market == "uk" else "articles-us")


def prime_event_slug(topic_key: str, market: str, year: int) -> str:
    return f"prime-big-deal-days-{topic_key}-{market}-{year}"


def _used_topics(state: dict, market: str) -> set[str]:
    used: set[str] = set()
    for day_state in state.get("days", {}).values():
        for row in (day_state.get(market) or {}).get("published", []):
            key = str(row.get("topic") or "").strip()
            if key:
                used.add(key)
    return used


def _market_state(state: dict, run_date: date, market: str) -> dict:
    day_state = state.setdefault("days", {}).setdefault(run_date.isoformat(), {})
    return day_state.setdefault(market, {"published": [], "attempted": []})



PRIME_AMAZON_SEARCHES = {
    "large-capacity-air-fryers": (
        "large capacity air fryer",
        "dual basket air fryer",
        "stacked air fryer",
        "family air fryer",
    ),
    "robot-vacuums": (
        "robot vacuum cleaner",
        "robot vacuum and mop",
        "self emptying robot vacuum",
        "robot vacuum for pet hair",
    ),
    "wireless-earbuds": (
        "wireless earbuds",
        "noise cancelling earbuds",
        "bluetooth earbuds",
        "sports wireless earbuds",
    ),
    "power-banks": (
        "power bank",
        "fast charging power bank",
        "USB C power bank",
        "portable charger",
    ),
    "smartwatches": (
        "smartwatch",
        "fitness smartwatch",
        "GPS smartwatch",
        "smartwatch with heart rate monitor",
    ),
    "coffee-machines": (
        "coffee machine",
        "bean to cup coffee machine",
        "espresso coffee machine",
        "pod coffee machine",
    ),
    "tvs": (
        "4K smart TV",
        "OLED TV",
        "QLED TV",
        "55 inch smart TV",
    ),
    "ssds": (
        "portable SSD",
        "NVMe SSD",
        "external SSD",
        "1TB SSD",
    ),
    "air-fryers": (
        "air fryer",
        "dual basket air fryer",
        "digital air fryer",
        "family air fryer",
    ),
    "tablets": (
        "tablet",
        "Android tablet",
        "10 inch tablet",
        "tablet with keyboard",
    ),
    "soundbars": (
        "soundbar",
        "Dolby Atmos soundbar",
        "TV soundbar",
        "soundbar with subwoofer",
    ),
    "security-cameras": (
        "security camera",
        "wireless security camera",
        "outdoor security camera",
        "home security camera",
    ),
}


def _amazon_search_url(query: str, market: str) -> str:
    host = "www.amazon.co.uk" if market == "uk" else "www.amazon.com"
    tag = "worthbuyin008-21" if market == "uk" else "worthbuyingus-20"
    return f"https://{host}/s?k={quote_plus(query)}&tag={tag}"




def _prime_membership_cta(market: str) -> str:
    if market == "uk":
        url = "https://www.amazon.co.uk/tryprimefree?tag=worthbuyin008-21"
        retailer = "Amazon UK"
        bounty_copy = "Eligible customers can check whether a Prime free trial is available."
    else:
        url = "https://www.amazon.com/tryprimefree?tag=worthbuyingus-20"
        retailer = "Amazon"
        bounty_copy = "Eligible customers can check whether a Prime free trial is available."

    return (
        '<aside class="wb-prime-signup" style="border:1px solid #f0a500;'
        'background:#fff8e8;border-radius:12px;padding:16px 18px;margin:18px 0;">'
        '<p style="margin:0 0 8px"><strong>Not a Prime member?</strong></p>'
        f'<p style="margin:0 0 12px">{html.escape(bounty_copy)} '
        'Prime eligibility and trial availability are determined by Amazon.</p>'
        f'<p style="margin:0"><a href="{html.escape(url, quote=True)}" '
        'rel="sponsored nofollow" style="display:inline-block;padding:11px 16px;'
        'background:#082f5b;color:#fff;text-decoration:none;border-radius:8px;'
        f'font-weight:700">Check {html.escape(retailer)} Prime eligibility</a></p>'
        '</aside>\n'
    )


def _amazon_search_fallback_content(topic: tuple, market: str, run_date: date) -> str:
    key, display, _query, _max_uk, _max_us, category, _kicker = daily.localise_topic(
        topic, market
    )
    region = "UK" if market == "uk" else "USA"
    retailer = "Amazon UK" if market == "uk" else "Amazon"
    searches = list(PRIME_AMAZON_SEARCHES.get(key) or ())
    if len(searches) < 3:
        searches = [display, f"best {display}", f"{display} deals", f"{display} Prime"]

    cards = []
    for index, search in enumerate(searches[:4], start=1):
        url = _amazon_search_url(search, market)
        cards.append(
            '<div style="border:1px solid #dfe6ee;border-radius:14px;padding:18px;'
            'margin:14px 0;background:#fff;">'
            f'<p style="margin:0 0 8px"><strong>{index}. {html.escape(search.title())}</strong></p>'
            '<p style="margin:6px 0">Browse the current Amazon results for this buying angle. '
            'Prices, Prime eligibility and promotions can change quickly, so check the live '
            'Amazon results before buying.</p>'
            '<p style="margin:14px 0 2px">'
            f'<a href="{html.escape(url, quote=True)}" rel="sponsored nofollow" '
            'style="display:inline-block;padding:11px 16px;background:#082f5b;'
            'color:#fff;text-decoration:none;border-radius:8px;font-weight:700">'
            f'Browse current {html.escape(retailer)} results</a></p></div>'
        )

    checks = [
        daily.localise_template_text(check, market)
        for check in daily.CATEGORY_CHECKS.get(
            category, daily.CATEGORY_CHECKS["Home & Kitchen"]
        )
    ]
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)
    checked = display_date(run_date)
    return (
        f"<p><strong>Shopping for {html.escape(display.lower())} during Prime Big Deal Days in the {region}? "
        "This Amazon-only fallback guide keeps the event coverage live even when Amazon's "
        "product-data API is temporarily unavailable.</strong></p>\n"
        f"<p>We checked the buying category on {html.escape(checked)}. Rather than inventing a price "
        "or discount without live API data, the links below take you to tracked Amazon searches so "
        "you can see the current products, prices and Prime eligibility directly on Amazon.</p>\n"
        f"{_prime_membership_cta(market)}"
        f"{daily.editorial_trust_html(market, checked)}"
        "<h2>Amazon searches worth checking now</h2>\n"
        + "".join(cards)
        + "<h2>How to choose the right option</h2>\n"
        f"<ul>{check_html}</ul>\n"
        "<h2>Why this Prime guide is Amazon-only</h2>\n"
        "<p>Prime Big Deal Days is an Amazon shopping event. These event-specific Worth Buying guides "
        "therefore use Amazon-only retailer links.</p>\n"
        "<h2>How we handle missing live product data</h2>\n"
        "<p>When Amazon's product-data API is unavailable, we do not publish unverified prices, "
        "discount percentages or product-specific claims. We publish tracked Amazon search links "
        "instead, so shoppers can verify the current offer directly.</p>\n"
        "<p><em>As an Amazon Associate we earn from qualifying purchases at no extra cost to you. "
        "Prices, promotions, Prime eligibility and availability can change quickly.</em></p>"
    )


def _amazon_prime_offers(topic: tuple, market: str) -> list:
    key, display, query, *_ = daily.localise_topic(topic, market)
    client = AmazonCreatorsClient.from_env(market)
    if client is None:
        raise RuntimeError(
            f"Amazon Creators API credentials are required for Prime product cards ({market})"
        )
    offers = client.search_offers(query, item_count=8)
    usable = []
    for offer in offers:
        if not offer.image_url:
            continue
        if not daily.relevant_product(offer.title, query):
            continue
        usable.append(offer)
        if len(usable) >= 4:
            break
    if len(usable) < 3:
        raise RuntimeError(
            f"Amazon returned only {len(usable)} usable {display} offers with product images"
        )
    return usable


def _amazon_only_prime_content(topic: tuple, market: str, run_date: date) -> str:
    key, display, query, _max_uk, _max_us, category, _kicker = daily.localise_topic(
        topic, market
    )
    region = "UK" if market == "uk" else "USA"
    retailer = "Amazon UK" if market == "uk" else "Amazon"
    symbol = "£" if market == "uk" else "$"
    offers = _amazon_prime_offers(topic, market)

    cards = []
    sections = []
    for index, offer in enumerate(offers, start=1):
        title = str(offer.title).strip()
        price = f"{symbol}{offer.price:,.2f}"
        url = str(offer.url).strip()
        image_markup = product_image_html(str(offer.image_url), title)
        cards.append(
            '<div style="border:1px solid #dfe6ee;border-radius:14px;padding:18px;'
            'margin:14px 0;background:#fff;">'
            f'{image_markup}'
            f'<p style="margin:0 0 8px"><strong>{index}. {html.escape(title)}</strong></p>'
            f'<p style="margin:6px 0"><strong>Amazon price checked:</strong> {html.escape(price)}</p>'
            '<p style="margin:6px 0">Prime eligibility, delivery and promotional pricing can change, '
            'so confirm the live Amazon listing before buying.</p>'
            '<p style="margin:14px 0 2px">'
            f'<a href="{html.escape(url, quote=True)}" rel="sponsored nofollow" '
            'style="display:inline-block;padding:11px 16px;background:#082f5b;'
            'color:#fff;text-decoration:none;border-radius:8px;font-weight:700">'
            f'Check {html.escape(retailer)} price</a></p></div>'
        )
        sections.append(
            f"<h3>{index}. {html.escape(title)}</h3>\n"
            f"<p>Amazon returned this product at {html.escape(price)} when the guide was generated. "
            "Check the exact model, specification, warranty, delivery, returns, Prime eligibility and "
            "current price on the live Amazon page before buying.</p>\n"
            f'<p><a href="{html.escape(url, quote=True)}" rel="sponsored nofollow">'
            f'View on {html.escape(retailer)}</a></p>\n'
        )

    checks = [
        daily.localise_template_text(check, market)
        for check in daily.CATEGORY_CHECKS.get(
            category, daily.CATEGORY_CHECKS["Home & Kitchen"]
        )
    ]
    check_html = "\n".join(f"<li>{html.escape(check)}</li>" for check in checks)
    checked = display_date(run_date)
    return (
        f"<p><strong>Shopping for {html.escape(display.lower())} during Prime Big Deal Days in the {region}? "
        "This event update is deliberately Amazon-only so every retailer link matches the Amazon event.</strong></p>\n"
        f"<p>We checked current Amazon products for {html.escape(display)} on {html.escape(checked)}. "
        "The product cards below use Amazon's current product title, price, product page and official primary image.</p>\n"
        f"{_prime_membership_cta(market)}"
        f"{daily.editorial_trust_html(market, checked)}"
        "<h2>Amazon products worth comparing</h2>\n"
        + "".join(cards)
        + "<h2>Current Amazon picks</h2>\n"
        + "".join(sections)
        + "<h2>How to choose the right option</h2>\n"
        f"<ul>{check_html}</ul>\n"
        "<h2>Why this Prime guide is Amazon-only</h2>\n"
        "<p>Prime Big Deal Days is an Amazon shopping event. These event-specific Worth Buying guides "
        "therefore use Amazon-only retailer links and Amazon product imagery.</p>\n"
        "<h2>How we choose these Prime picks</h2>\n"
        "<p>We use current Amazon catalogue data, practical buying checks and transparent pricing. "
        "We do not claim a Prime discount unless current Amazon data supports that claim.</p>\n"
        "<h2>Frequently asked questions</h2>\n"
        f"<h3>Are these {html.escape(display.lower())} definitely discounted?</h3>\n"
        "<p>No. Prices and promotions can change quickly. We show the Amazon price returned when the guide is generated, "
        "but you should check the live product page before buying.</p>\n"
        f"<h3>Why do all links go to {html.escape(retailer)}?</h3>\n"
        "<p>Because Prime Big Deal Days is an Amazon event, these Prime-specific guides do not mix in eBay links.</p>\n"
        "<p><em>As an Amazon Associate we earn from qualifying purchases at no extra cost to you. "
        "Prices, promotions, Prime eligibility and availability can change quickly.</em></p>"
    )


def make_prime_article_amazon_only(
    article: dict,
    *,
    topic: tuple,
    market: str,
    run_date: date,
) -> dict:
    article = deepcopy(article)
    fallback = False
    try:
        article["content_html"] = _amazon_only_prime_content(topic, market, run_date)
    except Exception as exc:
        if not _retryable_build_error(exc):
            raise
        fallback = True
        article["content_html"] = _amazon_search_fallback_content(
            topic, market, run_date
        )
        print(
            f"[prime-fallback] {market.upper()} {topic[0]}: Amazon Creators API "
            "credentials unavailable; publishing tracked Amazon search links without "
            "unverified product prices."
        )

    monetisation = article.setdefault("_monetisation", {})
    monetisation["networks"] = ["Amazon"]
    monetisation["retailer_mode"] = (
        "amazon-search-fallback" if fallback else "amazon-only"
    )
    generator = article.setdefault("_generator", {})
    generator["live_ebay_picks"] = False
    generator["prime_amazon_only"] = True
    generator["prime_amazon_search_fallback"] = fallback
    generator["pick_count"] = (
        min(4, len(PRIME_AMAZON_SEARCHES.get(topic[0]) or ()))
        if fallback
        else str(article.get("content_html") or "").count('class="wb-product-image"')
    )
    generator["retailer_mode"] = monetisation["retailer_mode"]
    article["youtube_short_points"] = (
        [
            "Tracked Amazon searches for current Prime Big Deal Days options",
            "No unverified prices or discount claims",
            "Check the live Amazon page for current Prime eligibility",
        ]
        if fallback
        else [
            "Amazon product images and current prices verified in the live guide",
            "Amazon-only Prime Big Deal Days retailer links",
            "Check the live Amazon page for current Prime eligibility",
        ]
    )
    return article
def validate_prime_article(article: dict, market: str) -> None:
    content = str(article.get("content_html") or "")
    lowered = content.casefold()
    if "ebay.co.uk" in lowered or "ebay.com" in lowered:
        raise RuntimeError("Prime event article contains an eBay link")
    required_host = "amazon.co.uk" if market == "uk" else "amazon.com"
    if required_host not in lowered:
        raise RuntimeError(f"Prime event article contains no {required_host} link")
    networks = list((article.get("_monetisation") or {}).get("networks") or [])
    if networks != ["Amazon"]:
        raise RuntimeError(f"Prime event networks must be Amazon-only, got {networks}")
    expected_prime_path = "amazon.co.uk/tryprimefree" if market == "uk" else "amazon.com/tryprimefree"
    if expected_prime_path not in lowered:
        raise RuntimeError(
            f"Prime event article must contain the tracked Prime signup CTA for {market}"
        )
    generator = article.get("_generator") or {}
    if generator.get("prime_amazon_search_fallback"):
        expected_tag = "worthbuyin008-21" if market == "uk" else "worthbuyingus-20"
        if lowered.count("/s?k=") < 3:
            raise RuntimeError(
                "Prime fallback article must contain at least 3 Amazon search links"
            )
        if f"tag={expected_tag}" not in lowered:
            raise RuntimeError(
                f"Prime fallback article is missing the Amazon Associate tag for {market}"
            )
        if "amazon price checked:" in lowered:
            raise RuntimeError(
                "Prime fallback article must not claim a checked Amazon product price"
            )
        return

    image_count = lowered.count('m.media-amazon.com') + lowered.count('images-na.ssl-images-amazon.com') + lowered.count('images-eu.ssl-images-amazon.com')
    if image_count < 3:
        raise RuntimeError(
            f"Prime event article must contain at least 3 Amazon product images; found {image_count}"
        )


def _event_banner(run_date: date, market: str) -> str:
    region = "UK" if market == "uk" else "USA"
    checked = display_date(run_date)
    return (
        '<aside class="wb-prime-big-deal-days" data-event="2026" '
        'style="border-left:4px solid #f0a500;background:#fff8e8;'
        'padding:16px 18px;margin:18px 0;">'
        f'<p style="margin-top:0"><strong>{EVENT_NAME} price check — '
        f'{html.escape(checked)}.</strong></p>'
        f'<p>For this {region} update we rechecked current Amazon options '
        'during Amazon\'s 6–7 October shopping event. All outbound retailer links '
        'in this Prime guide go to Amazon. Exact prices are shown only where current '
        'Amazon data verifies them. Inclusion here does not mean every item is a '
        'Prime-exclusive discount, so compare the live Amazon price and terms before buying.</p>'
        '</aside>\n'
    )


def _insert_event_banner(content: str, banner: str) -> str:
    if 'class="wb-prime-big-deal-days"' in content:
        return re.sub(
            r'<aside class="wb-prime-big-deal-days"[\s\S]*?</aside>\s*',
            banner,
            content,
            count=1,
            flags=re.IGNORECASE,
        )
    close = content.find("</p>")
    if close < 0:
        return banner + content
    close += len("</p>")
    return content[:close] + "\n" + banner + content[close:]


def decorate_prime_article(
    article: dict,
    *,
    topic: tuple,
    market: str,
    run_date: date,
    refreshing: bool,
) -> dict:
    article = deepcopy(article)
    _, display, *_ = daily.localise_topic(topic, market)
    region = "UK" if market == "uk" else "USA"
    checked = display_date(run_date)

    restore_fields = {
        key: deepcopy(article.get(key))
        for key in (
            "title",
            "labels",
            "hero_image_kicker",
            "pinterest_title",
            "pinterest_subtitle",
            "x_image_title",
            "x_kicker",
            "x_subtitle",
            "x_text",
            "hero_visual_revision",
        )
    }
    restore_fields["_seo"] = deepcopy(article.get("_seo") or {})

    article["_event"] = {
        "key": EVENT_KEY,
        "name": EVENT_NAME,
        "event_start": EVENT_START.isoformat(),
        "event_end": EVENT_END.isoformat(),
        "checked_date": run_date.isoformat(),
        "restore": restore_fields,
    }

    article["title"] = (
        f"{EVENT_NAME}: {display} Worth Comparing in the {region} (2026)"
    )
    article["labels"] = list(dict.fromkeys(
        list(article.get("labels") or [])
        + [EVENT_NAME, "Deals"]
    ))
    article["hero_image_kicker"] = "PRIME BIG DEAL DAYS"
    article["pinterest_title"] = f"{EVENT_NAME}: {display} Worth Comparing"
    article["pinterest_subtitle"] = (
        f"Current Amazon options checked {checked}"
    )
    article["x_image_title"] = f"{display} Worth Comparing"
    article["x_kicker"] = "PRIME BIG DEAL DAYS"
    article["x_subtitle"] = f"Prices checked {checked}"
    article["x_text"] = (
        f"🛒 {EVENT_NAME}: {display}\n\n"
        "We checked current Amazon options for the event. "
        "Exact prices are only used where current Amazon data verifies them.\n\n"
        "See what is worth comparing 👇\n"
        "Read the guide 🔗 {url}\n"
        "#PrimeBigDealDays #WorthBuying"
    )
    article["hero_visual_revision"] = (
        f"prime-big-deal-days-{market}-{run_date.isoformat()}"
    )
    article["content_html"] = _insert_event_banner(
        str(article.get("content_html") or ""),
        _event_banner(run_date, market),
    )

    seo = article.setdefault("_seo", {})
    seo["event"] = EVENT_NAME
    seo["event_dates"] = "6–7 October 2026"
    seo["last_checked_iso"] = run_date.isoformat()
    seo["primary_keyword"] = (
        f"prime big deal days {display.lower()} {region.lower()} 2026"
    )
    secondaries = list(seo.get("secondary_keywords") or [])
    secondaries[:0] = [
        f"{display.lower()} prime big deal days",
        f"{display.lower()} deals october 2026",
    ]
    seo["secondary_keywords"] = list(dict.fromkeys(secondaries))
    seo["description"] = (
        f"{EVENT_NAME} {display.lower()} price check for the {region}, "
        f"updated {checked} using current retailer data and practical buying checks."
    )

    monetisation = article.setdefault("_monetisation", {})
    monetisation["event"] = EVENT_NAME
    monetisation["event_mode"] = True
    monetisation["primary_goal"] = "qualified-affiliate-click"
    monetisation["networks"] = ["Amazon"]
    monetisation.setdefault("retailer_mode", "amazon-only")

    article["_promotion"] = {
        "daily_featured_date": run_date.isoformat(),
        "promotion_token": (
            f"{run_date.isoformat()}:prime-big-deal-days:{market}:{article['slug']}"
        ),
        "return_to_top": True,
        "is_refresh": refreshing,
    }
    article["source_sha"] = (
        f"{run_date.isoformat()}-{topic[0]}-{market}-prime-big-deal-days-amazon-v2"
    )
    return article


def _retryable_build_error(exc: Exception) -> bool:
    """Return True for environment failures that a later scheduled run can fix."""
    message = f"{type(exc).__name__}: {exc}".casefold()
    return "amazon creators api credentials are required" in message


def generate_one_market(
    state: dict,
    *,
    market: str,
    run_date: date,
    year: int,
) -> dict | None:
    market_state = _market_state(state, run_date, market)
    published = market_state.setdefault("published", [])
    attempted = market_state.setdefault("attempted", [])
    if len(published) >= TARGET_PER_MARKET_PER_DAY:
        print(
            f"[prime-skip] {market.upper()}: already has "
            f"{len(published)} Prime guide(s) for {run_date}"
        )
        return None

    attempted_keys = {
        str(row.get("topic") or "") if isinstance(row, dict) else str(row)
        for row in attempted
    }
    used = _used_topics(state, market)
    candidates = list(DAY_PLANS[run_date])
    # If a topic was used yesterday, prefer a different commercial category.
    ordered = [key for key in candidates if key not in used] + [
        key for key in candidates if key in used
    ]

    for key in ordered:
        if key in attempted_keys:
            continue
        topic = topic_by_key(key)
        try:
            article = daily.build_article(topic, market, year)
            article = make_prime_article_amazon_only(
                article,
                topic=topic,
                market=market,
                run_date=run_date,
            )
        except Exception as exc:
            if _retryable_build_error(exc):
                print(
                    f"[prime-retryable] {market.upper()} {key}: "
                    f"{type(exc).__name__}: {exc}; topic remains eligible for a later run"
                )
                # Stop this market run immediately. Trying every remaining topic
                # cannot succeed while the shared Amazon credentials are missing,
                # and none of those topics should be poisoned as "attempted".
                return None

            attempted.append({
                "topic": key,
                "status": "build-error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"[prime-warning] {market.upper()} {key}: {type(exc).__name__}: {exc}")
            continue

        article["slug"] = prime_event_slug(key, market, year)
        directory = article_dir(market)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{article['slug']}.json"
        refreshing = target.exists()
        article = decorate_prime_article(
            article,
            topic=topic,
            market=market,
            run_date=run_date,
            refreshing=refreshing,
        )
        validate_prime_article(article, market)
        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        row = {
            "slot": len(published) + 1,
            "topic": key,
            "slug": article["slug"],
            "title": article["title"],
            "action": "refreshed" if refreshing else "created",
            "pick_count": int(article.get("_generator", {}).get("pick_count") or 0),
        }
        published.append(row)
        attempted.append({"topic": key, "status": "published"})
        print(
            f"[prime-{row['action']}] {market.upper()} slot {row['slot']}/"
            f"{TARGET_PER_MARKET_PER_DAY}: {article['title']} "
            f"({row['pick_count']} Amazon-only links)"
        )
        return row

    print(
        f"[prime-warning] {market.upper()}: no remaining candidate produced "
        "enough verified live listings"
    )
    return None



def repair_existing_event_articles(state: dict, run_date: date) -> int:
    changed = 0
    for market in ("uk", "us"):
        market_state = _market_state(state, run_date, market)
        for row in market_state.get("published", []):
            key = str(row.get("topic") or "").strip()
            if not key:
                continue
            topic = topic_by_key(key)
            try:
                base_article = daily.build_article(topic, market, run_date.year)
                original_slug = str(base_article.get("slug") or "").strip()
                article = make_prime_article_amazon_only(
                    base_article,
                    topic=topic,
                    market=market,
                    run_date=run_date,
                )
                article["slug"] = prime_event_slug(key, market, run_date.year)
                article = decorate_prime_article(
                    article,
                    topic=topic,
                    market=market,
                    run_date=run_date,
                    refreshing=True,
                )
                validate_prime_article(article, market)
            except Exception as exc:
                print(
                    f"[prime-repair-warning] {market.upper()} {key}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            target = article_dir(market) / f"{article['slug']}.json"
            rendered = json.dumps(article, indent=2, ensure_ascii=False) + "\n"
            previous = target.read_text(encoding="utf-8") if target.exists() else ""
            if rendered != previous:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rendered, encoding="utf-8")
                changed += 1
                print(f"[prime-repaired] {market.upper()} {key}: Amazon-only")

            previous_row_slug = str(row.get("slug") or "").strip()
            if (
                original_slug
                and previous_row_slug
                and previous_row_slug != article["slug"]
                and previous_row_slug == original_slug
            ):
                old_target = article_dir(market) / f"{original_slug}.json"
                evergreen = json.dumps(base_article, indent=2, ensure_ascii=False) + "\n"
                old_previous = (
                    old_target.read_text(encoding="utf-8")
                    if old_target.exists()
                    else ""
                )
                if evergreen != old_previous:
                    old_target.write_text(evergreen, encoding="utf-8")
                    changed += 1
                    print(
                        f"[prime-restored-evergreen] {market.upper()} {key}: "
                        f"{original_slug}"
                    )

            row["slug"] = article["slug"]
            row["title"] = article["title"]
            row["pick_count"] = int(
                article.get("_generator", {}).get("pick_count") or 0
            )
            row["action"] = "refreshed"
            row["retailer"] = "Amazon"
    return changed


def cleanup_event_articles(state: dict, run_date: date) -> int:
    if state.get("cleanup", {}).get("completed"):
        print("[prime-cleanup-skip] cleanup already completed")
        return 0

    changed = 0
    for market in ("uk", "us"):
        directory = article_dir(market)
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            article = load_json(path)
            event = article.get("_event") or {}
            if event.get("key") != EVENT_KEY:
                continue
            if str(article.get("slug") or "").startswith("prime-big-deal-days-"):
                content = str(article.get("content_html") or "")
                content = re.sub(
                    r'\s*<aside class="wb-prime-big-deal-days"[\s\S]*?</aside>\s*',
                    "\n",
                    content,
                    count=1,
                    flags=re.IGNORECASE,
                )
                expired = (
                    '<aside class="wb-prime-big-deal-days-ended" '
                    'style="border-left:4px solid #777;background:#f6f6f6;'
                    'padding:16px 18px;margin:18px 0;">'
                    '<p><strong>Prime Big Deal Days has ended.</strong></p>'
                    '<p>This guide is kept as an event archive. Check the live Amazon '
                    'pages for current prices, availability and Prime eligibility.</p>'
                    '</aside>\n'
                )
                article["content_html"] = expired + content
                promotion = article.setdefault("_promotion", {})
                promotion["return_to_top"] = False
                article["hero_visual_revision"] = (
                    f"post-prime-archive-{run_date.isoformat()}"
                )
                article["source_sha"] = (
                    f"{run_date.isoformat()}-{market}-{article['slug']}-post-prime-archive-v1"
                )
                path.write_text(
                    json.dumps(article, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                changed += 1
                continue

            restore = event.get("restore") or {}
            for key in (
                "title",
                "labels",
                "hero_image_kicker",
                "pinterest_title",
                "pinterest_subtitle",
                "x_image_title",
                "x_kicker",
                "x_subtitle",
                "x_text",
            ):
                if key in restore:
                    article[key] = deepcopy(restore[key])

            if restore.get("_seo") is not None:
                article["_seo"] = deepcopy(restore["_seo"])
                article["_seo"]["last_checked_iso"] = str(
                    (article.get("_promotion") or {}).get("daily_featured_date")
                    or article["_seo"].get("last_checked_iso")
                    or ""
                )

            content = str(article.get("content_html") or "")
            content = re.sub(
                r'\s*<aside class="wb-prime-big-deal-days"[\s\S]*?</aside>\s*',
                "\n",
                content,
                count=1,
                flags=re.IGNORECASE,
            )
            article["content_html"] = content
            article["hero_visual_revision"] = (
                f"post-prime-refresh-{run_date.isoformat()}"
            )
            article["source_sha"] = (
                f"{run_date.isoformat()}-{market}-{article['slug']}-post-prime-v1"
            )
            article.pop("_event", None)
            path.write_text(
                json.dumps(article, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            changed += 1

    state["cleanup"] = {
        "completed": True,
        "date": run_date.isoformat(),
        "articles_restored": changed,
    }
    print(f"[prime-cleanup] restored {changed} article(s) to evergreen presentation")
    return changed


def run_for_date(run_date: date) -> int:
    state = load_json(STATE_PATH)
    state.setdefault("event", {
        "key": EVENT_KEY,
        "start": EVENT_START.isoformat(),
        "end": EVENT_END.isoformat(),
        "target_per_market_per_day": TARGET_PER_MARKET_PER_DAY,
    })

    if event_active(run_date):
        changed = repair_existing_event_articles(state, run_date)
        for market in ("uk", "us"):
            if generate_one_market(
                state,
                market=market,
                run_date=run_date,
                year=run_date.year,
            ):
                changed += 1
        save_json(STATE_PATH, state)
        return changed

    if run_date >= CLEANUP_DATE:
        changed = cleanup_event_articles(state, run_date)
        save_json(STATE_PATH, state)
        return changed

    print(
        f"[prime-skip] {run_date}: event mode only runs "
        f"{EVENT_START} through {EVENT_END}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        help="Override London date for deterministic testing/manual recovery (YYYY-MM-DD)",
    )
    args = parser.parse_args()
    run_date = (
        date.fromisoformat(args.date)
        if args.date
        else datetime.now(LONDON).date()
    )
    changed = run_for_date(run_date)
    print(f"Prime Big Deal Days run complete: {changed} article(s) changed.")


if __name__ == "__main__":
    main()
