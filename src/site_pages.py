from __future__ import annotations

import html
from src.price_tracking import valid_observations
from src.price_charts import chart_html
import json
from datetime import date
from statistics import median
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

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

TOPIC_TO_CLUSTER = {
    topic: cluster
    for cluster, topics in AUTHORITY_CLUSTERS.items()
    for topic in topics
}

MARKET = {
    "uk": {
        "site": "Worth Buying UK",
        "region": "UK",
        "articles": ROOT / "articles",
        "published": ROOT / "state" / "articles_published.json",
        "page_state": ROOT / "state" / "site_pages_uk.json",
    },
    "us": {
        "site": "Worth Buying USA",
        "region": "USA",
        "articles": ROOT / "articles-us",
        "published": ROOT / "state" / "articles_us_published.json",
        "page_state": ROOT / "state" / "site_pages_us.json",
    },
}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _article_date(article: dict) -> str:
    checked = str((article.get("_seo") or {}).get("last_checked_iso") or "").strip()
    if checked:
        return checked[:10]
    source = str(article.get("source_sha") or "")
    return source[:10] if len(source) >= 10 else ""


def load_catalog(market: str) -> list[dict]:
    cfg = MARKET[market]
    published = _load_json(cfg["published"])
    catalog: list[dict] = []

    for slug, state in published.items():
        if not isinstance(state, dict):
            continue
        if state.get("status") != "published" or not state.get("url"):
            continue

        source_file = str(state.get("source_file") or f"{slug}.json")
        path = cfg["articles"] / source_file
        if not path.exists():
            continue
        article = _load_json(path)
        topic = str((article.get("_generator") or {}).get("topic") or "").strip()
        cluster = str((article.get("_seo") or {}).get("authority_cluster") or "").strip()
        if not cluster:
            cluster = TOPIC_TO_CLUSTER.get(topic, "")
        if cluster not in AUTHORITY_CLUSTERS:
            continue

        catalog.append(
            {
                "slug": slug,
                "title": str(article.get("title") or state.get("title") or slug),
                "url": str(state["url"]),
                "cluster": cluster,
                "topic": topic,
                "description": str((article.get("_seo") or {}).get("description") or ""),
                "checked": _article_date(article),
                "monetised": bool(article.get("_monetisation")),
            }
        )

    catalog.sort(key=lambda row: (row["checked"], row["title"]), reverse=True)
    return catalog


def methodology_page(market: str) -> dict:
    cfg = MARKET[market]
    region = cfg["region"]
    site = cfg["site"]
    content = (
        '<div style="max-width:900px;margin:0 auto;line-height:1.65">'
        f'<p><strong>{site}</strong> is an independent, affiliate-funded buying-guide site. '
        f'Our purpose is to help shoppers in the {region} narrow large product markets into a smaller '
        'set of options worth comparing.</p>'
        '<h2>How we choose products</h2>'
        '<p>Our automated research uses current retailer and marketplace data, product relevance, '
        'seller-quality signals, realistic pricing checks, condition information and, where enough '
        'observations exist, our own recorded price history for the same listing.</p>'
        '<p>Weak, unrelated or suspicious marketplace listings are filtered out. We do not rank an item '
        'simply because a retailer displays a large crossed-out reference price or because it offers a '
        'higher affiliate commission.</p>'
        '<h2>What our recommendations mean</h2>'
        '<p>Most Worth Buying daily guides are data-led comparisons, not laboratory tests. We do not claim '
        'hands-on testing unless a page explicitly says that testing took place. For performance, safety '
        'or durability questions, readers should also consult independent testing of the exact model.</p>'
        '<h2>How Worth Buying makes money</h2>'
        '<p>Some links to retailers are affiliate links. If a reader buys after using one of those links, '
        'Worth Buying may receive a commission at no extra cost to the reader. Retailers do not pay to be '
        'included in our shortlists, and commission level is not used as a product-quality score.</p>'
        '<h2>Prices and updates</h2>'
        '<p>Prices, seller feedback, stock and promotions change. Our automated guides record when they were '
        'last checked and strong commercial guides are refreshed rather than abandoned as one-off posts. '
        'The live retailer page remains the final source for price, availability, warranty and returns.</p>'
        '<h2>Our editorial priority</h2>'
        '<p>We prioritise useful commercial-intent content: exact product comparisons, value checks, '
        'condition and seller quality, retailer comparisons and practical buying advice. The aim is to '
        'earn trust first; affiliate revenue follows only when a reader finds the comparison useful.</p>'
        f'<p><em>Methodology last reviewed: {date.today().isoformat()}.</em></p>'
        '</div>'
    )
    return {
        "key": "methodology",
        "title": "How Worth Buying Chooses Products",
        "content": content,
    }


def cluster_page(cluster: str, rows: list[dict], market: str) -> dict:
    cfg = MARKET[market]
    region = cfg["region"]
    site = cfg["site"]
    cards: list[str] = []

    for row in rows:
        checked = (
            f'<br><small>Last checked: {html.escape(row["checked"])}</small>'
            if row.get("checked")
            else ""
        )
        description = (
            f'<p style="margin:6px 0 0">{html.escape(row["description"])}</p>'
            if row.get("description")
            else ""
        )
        cards.append(
            '<li style="margin:0 0 18px">'
            f'<a href="{html.escape(row["url"], quote=True)}"><strong>'
            f'{html.escape(row["title"])}</strong></a>'
            f'{description}{checked}</li>'
        )

    if not cards:
        cards.append(
            '<li>New guides for this category are being added and refreshed automatically.</li>'
        )

    content = (
        '<div style="max-width:900px;margin:0 auto;line-height:1.65">'
        f'<p><strong>{html.escape(cluster)} buying guides for the {region}.</strong> '
        'This hub groups together our current commercial guides so you can compare related products '
        'without jumping between unrelated topics.</p>'
        '<p>Our strongest guides are refreshed as prices, seller signals and demand change. '
        'Use the individual guide for current retailer checks and affiliate links.</p>'
        f'<h2>Latest {html.escape(cluster)} guides</h2>'
        f'<ul style="padding-left:22px">{"".join(cards)}</ul>'
        '<h2>How these guides are funded</h2>'
        f'<p>{site} may earn affiliate commission from qualifying retailer purchases at no extra cost '
        'to the reader. Products are filtered for relevance and quality before affiliate revenue is considered.</p>'
        '<p><a href="/p/how-worth-buying-chooses-products.html">Read how Worth Buying chooses products</a></p>'
        '</div>'
    )
    return {
        "key": "cluster-" + cluster.casefold().replace("&", "and").replace(" ", "-"),
        "title": f"{cluster} Buying Guides",
        "content": content,
    }


def _money(value: float, currency: str) -> str:
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, f"{currency} ")
    return f"{symbol}{value:,.2f}"


def price_watch_page(market: str) -> dict:
    cfg = MARKET[market]
    history = _load_json(ROOT / "state" / "daily_price_history.json")
    published = _load_json(cfg["published"])
    rows: list[dict] = []

    prefix = f"daily|{market}|"
    for key, entry in history.items():
        if not str(key).startswith(prefix) or not isinstance(entry, dict):
            continue
        observations = valid_observations(entry, "GBP" if market == "uk" else "USD")
        prices = []
        currency = ""
        for obs in observations:
            try:
                prices.append(float(obs.get("price")))
            except (TypeError, ValueError):
                continue
            currency = str(obs.get("currency") or currency)

        if len(prices) < 3:
            continue
        current = prices[-1]
        typical = float(median(prices))
        if typical <= 0:
            continue
        drop = ((typical - current) / typical) * 100
        if drop < 5:
            continue

        slug = str(entry.get("article_slug") or "")
        article_url = str((published.get(slug) or {}).get("url") or "")
        rows.append(
            {
                "title": str(entry.get("title") or "Product listing"),
                "current": current,
                "median": typical,
                "drop": drop,
                "currency": currency,
                "checks": len(prices),
                "article_url": article_url,
                "chart": chart_html(key, entry, market),
                "last_checked": observations[-1]["date"],
            }
        )

    rows.sort(key=lambda row: row["drop"], reverse=True)
    rows = rows[:20]

    if rows:
        items = []
        for row in rows:
            title = html.escape(row["title"])
            if row["article_url"]:
                title = (
                    f'<a href="{html.escape(row["article_url"], quote=True)}">'
                    f'{title}</a>'
                )
            items.append(
                '<li style="margin:0 0 16px">'
                f'<strong>{title}</strong><br>'
                f'Current observed price: {_money(row["current"], row["currency"])} · '
                f'Observed median: {_money(row["median"], row["currency"])} · '
                f'<strong>{row["drop"]:.0f}% below observed median</strong> '
                f'({row["checks"]} checks; last observed {row["last_checked"]})'
                f'{row["chart"]}</li>'
            )
        body = '<ul>' + "".join(items) + '</ul>'
    else:
        body = (
            '<p>WorthBuying is building its own price history as listings are rechecked. '
            'Meaningful observed price drops will appear here once enough repeat observations exist.</p>'
        )

    content = (
        '<div style="max-width:900px;margin:0 auto;line-height:1.65">'
        '<p><strong>WorthBuying Price Watch</strong> uses our own repeat observations of the same '
        'marketplace listings. It is not based on a retailer\'s crossed-out RRP.</p>'
        '<p>We only show an observed drop after at least three price checks and when the current '
        'price is at least 5% below the median of our observations. Prices can change at any time.</p>'
        f'{body}'
        '<p><a href="/p/how-worth-buying-chooses-products.html">'
        'Read our full product-selection and affiliate methodology</a></p>'
        '</div>'
    )
    return {
        "key": "price-watch",
        "title": "WorthBuying Price Watch",
        "content": content,
    }


def build_pages(market: str) -> list[dict]:
    if market not in MARKET:
        raise ValueError("market must be uk or us")
    catalog = load_catalog(market)
    pages = [methodology_page(market), price_watch_page(market)]
    for cluster in AUTHORITY_CLUSTERS:
        rows = [row for row in catalog if row["cluster"] == cluster]
        pages.append(cluster_page(cluster, rows, market))
    return pages
