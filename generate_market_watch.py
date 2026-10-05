from __future__ import annotations

import html
from src.price_tracking import valid_observations
from src.price_charts import chart_html
import json
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
LONDON = ZoneInfo("Europe/London")
HISTORY = ROOT / "state" / "daily_price_history.json"
STATE = ROOT / "state" / "monthly_market_watch.json"
MIN_TRACKED_PRODUCTS = 8
MIN_MOVERS = 3


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


def money(value: float, currency: str) -> str:
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, f"{currency} ")
    return f"{symbol}{value:,.2f}"


def market_rows(market: str) -> tuple[list[dict], int]:
    history = load_json(HISTORY)
    state_path = ROOT / "state" / (
        "articles_published.json" if market == "uk" else "articles_us_published.json"
    )
    published = load_json(state_path)
    prefix = f"daily|{market}|"
    rows: list[dict] = []
    eligible_count = 0

    for key, entry in history.items():
        if not str(key).startswith(prefix) or not isinstance(entry, dict):
            continue

        observations = valid_observations(entry, "GBP" if market == "uk" else "USD")
        valid: list[tuple[float, str]] = []
        for obs in observations:
            try:
                value = float(obs.get("price"))
            except (TypeError, ValueError):
                continue
            valid.append((value, str(obs.get("currency") or "")))

        if len(valid) < 3:
            continue
        eligible_count += 1

        prices = [value for value, _ in valid]
        current = prices[-1]
        typical = float(median(prices))
        if typical <= 0:
            continue
        change_pct = ((current - typical) / typical) * 100.0

        slug = str(entry.get("article_slug") or "")
        guide_url = str((published.get(slug) or {}).get("url") or "")
        rows.append(
            {
                "title": str(entry.get("title") or "Tracked product"),
                "current": current,
                "median": typical,
                "change_pct": round(change_pct, 1),
                "currency": valid[-1][1],
                "checks": len(valid),
                "guide_url": guide_url,
                "chart": chart_html(key, entry, market),
            }
        )

    rows.sort(key=lambda row: abs(row["change_pct"]), reverse=True)
    return rows, eligible_count


def render_market_watch(market: str, now: datetime) -> dict | None:
    rows, eligible_count = market_rows(market)
    movers = [row for row in rows if abs(float(row["change_pct"])) >= 5]
    if eligible_count < MIN_TRACKED_PRODUCTS or len(movers) < MIN_MOVERS:
        print(
            f"[market-watch-skip] {market.upper()}: "
            f"{eligible_count} products have 3+ checks; {len(movers)} moved at least 5%. "
            f"Need {MIN_TRACKED_PRODUCTS}/{MIN_MOVERS}."
        )
        return None

    region = "UK" if market == "uk" else "USA"
    month = now.strftime("%B %Y")
    slug = f"worthbuying-market-watch-{market}-{now:%Y-%m}"
    biggest_falls = sorted(
        [row for row in movers if row["change_pct"] < 0],
        key=lambda row: row["change_pct"],
    )[:8]
    biggest_rises = sorted(
        [row for row in movers if row["change_pct"] > 0],
        key=lambda row: row["change_pct"],
        reverse=True,
    )[:5]

    def list_html(items: list[dict], falling: bool) -> str:
        if not items:
            return "<p>No tracked products met this threshold this month.</p>"
        parts = ["<ul>"]
        for row in items:
            direction = "below" if falling else "above"
            pct = abs(float(row["change_pct"]))
            name = html.escape(row["title"])
            if row["guide_url"]:
                name = (
                    f'<a href="{html.escape(row["guide_url"], quote=True)}">'
                    f'{name}</a>'
                )
            parts.append(
                "<li>"
                f"<strong>{name}</strong> — {pct:.0f}% {direction} its observed median; "
                f"current observation {money(row['current'], row['currency'])}, "
                f"median {money(row['median'], row['currency'])} "
                f"across {row['checks']} checks."
                f"{row.get('chart', '')}"
                "</li>"
            )
        parts.append("</ul>")
        return "".join(parts)

    fall_html = list_html(biggest_falls, True)
    rise_html = list_html(biggest_rises, False)
    tracked_count = eligible_count
    mover_count = len(movers)

    content = (
        f"<p><strong>WorthBuying Market Watch for {html.escape(month)}</strong> uses our own repeated "
        f"price observations across {tracked_count} tracked product listings in the {region}. "
        "It does not treat retailer crossed-out RRPs as price history.</p>"
        f"<p>This month, {mover_count} tracked listings were at least 5% away from their observed "
        "median after three or more checks. This is a snapshot of individual listings, not a claim "
        "about the whole retail market.</p>"
        "<h2>Tracked prices that moved lower</h2>"
        f"{fall_html}"
        "<h2>Tracked prices that moved higher</h2>"
        f"{rise_html}"
        "<h2>How to use this data</h2>"
        "<p>A lower observed price can be a useful buying signal, but condition, exact model, seller "
        "quality, warranty, delivery and returns still matter. Follow the linked buying guide to compare "
        "current options before purchasing.</p>"
        "<h2>Methodology</h2>"
        "<p>We record at most one observation per listing per day when that listing appears in our "
        "automated buying-guide research. We only include a listing in this report after at least three "
        "valid observations on distinct dates, with a latest check no older than seven days, and we compare its most recent observation with the median of our recorded "
        "history. Listings can disappear or change, so this data should not be treated as a market-wide "
        "price index.</p>"
        "<p><strong>Affiliate disclosure:</strong> linked WorthBuying guides may contain affiliate links. "
        "A qualifying purchase may earn WorthBuying a commission at no extra cost to the reader.</p>"
    )

    falls = len(biggest_falls)
    short_points = [
        f"{tracked_count} listings had enough WorthBuying price history",
        f"{mover_count} moved at least 5% from their observed median",
        f"{falls} of the biggest movers shown were lower-priced observations",
    ]

    return {
        "slug": slug,
        "source_sha": f"{now.date().isoformat()}-market-watch-{market}-v1",
        "mode": "publish",
        "title": f"WorthBuying Market Watch: {region} Price Moves ({month})",
        "primary_category": "Shopping Data",
        "labels": ["Shopping Data", "Price Watch", "Buying Guides", region],
        "ai_visual_enabled": True,
        "pinterest_enabled": True,
        "hero_image_kicker": "WORTHBUYING MARKET WATCH",
        "pinterest_title": f"WorthBuying Market Watch — {region} {month}",
        "pinterest_subtitle": "Original WorthBuying price observations and meaningful moves",
        "x_image_title": f"{region} Market Watch",
        "x_kicker": "ORIGINAL WORTHBUYING DATA",
        "x_subtitle": f"{mover_count} tracked listings moved 5%+ from their observed median",
        "x_text": (
            f"📊 New WorthBuying Market Watch: {region}\n\n"
            f"Our own tracker found {mover_count} listings at least 5% away from their observed median.\n\n"
            "See the original data story 👇\n"
            "Read the report 🔗 {url}\n"
            "#PriceWatch #WorthBuying"
        ),
        "content_html": content,
        "youtube_short_points": short_points,
        "_seo": {
            "version": "market-watch-v1",
            "target_country": "GB" if market == "uk" else "US",
            "language": "en-GB" if market == "uk" else "en-US",
            "primary_keyword": f"{region.lower()} product price trends {now:%B %Y}".lower(),
            "secondary_keywords": [
                "WorthBuying price watch",
                f"{region.lower()} shopping price data",
                "product price changes",
            ],
            "description": (
                f"Original WorthBuying price observations for {region} shoppers in {month}, "
                "including meaningful moves versus our observed listing medians."
            ),
            "search_intent": "informational commercial",
            "original_data": True,
            "last_checked_iso": now.date().isoformat(),
        },
        "_monetisation": {
            "version": "affiliate-funnel-v1",
            "primary_goal": "internal-link-to-money-guide",
            "commercial_intent": "medium",
            "direct_affiliate_links": False,
        },
        "_generator": {
            "market": market,
            "content_type": "original-market-data",
            "tracked_products": tracked_count,
            "movers": mover_count,
            "article_directory": "articles" if market == "uk" else "articles-us",
        },
    }


def main() -> None:
    now = datetime.now(LONDON)
    month_key = now.strftime("%Y-%m")
    state = load_json(STATE)
    created = 0

    for market in ("uk", "us"):
        if str((state.get(market) or {}).get("month") or "") == month_key:
            print(f"[market-watch-skip] {market.upper()}: {month_key} already handled")
            continue

        article = render_market_watch(market, now)
        if article is None:
            continue

        article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
        article_dir.mkdir(parents=True, exist_ok=True)
        target = article_dir / f"{article['slug']}.json"
        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state[market] = {
            "month": month_key,
            "slug": article["slug"],
            "title": article["title"],
            "tracked_products": article["_generator"]["tracked_products"],
            "movers": article["_generator"]["movers"],
        }
        created += 1
        print(f"[market-watch-created] {market.upper()}: {target.relative_to(ROOT)}")

    save_json(STATE, state)
    print(f"Monthly market watch complete: {created} article(s) created.")


if __name__ == "__main__":
    main()
