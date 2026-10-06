from __future__ import annotations

import argparse
import html
import json
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import generate_daily_articles as daily


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


def _event_banner(run_date: date, market: str) -> str:
    region = "UK" if market == "uk" else "USA"
    checked = display_date(run_date)
    return (
        '<aside class="wb-prime-big-deal-days" data-event="2026" '
        'style="border-left:4px solid #f0a500;background:#fff8e8;'
        'padding:16px 18px;margin:18px 0;">'
        f'<p style="margin-top:0"><strong>{EVENT_NAME} price check — '
        f'{html.escape(checked)}.</strong></p>'
        f'<p>For this {region} update we rechecked current Amazon and eBay options '
        'during Amazon\'s 6–7 October shopping event. Exact prices are shown only '
        'where current retailer data returned them. Inclusion here does not mean '
        'every item is a Prime-exclusive discount, so compare the live retailer '
        'price and terms before buying.</p>'
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
        f"Current Amazon & eBay prices checked {checked}"
    )
    article["x_image_title"] = f"{display} Worth Comparing"
    article["x_kicker"] = "PRIME BIG DEAL DAYS"
    article["x_subtitle"] = f"Prices checked {checked}"
    article["x_text"] = (
        f"🛒 {EVENT_NAME}: {display}\n\n"
        "We checked current Amazon and eBay options and filtered out weak listings. "
        "Exact prices are only used where live retailer data verifies them.\n\n"
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

    article["_promotion"] = {
        "daily_featured_date": run_date.isoformat(),
        "promotion_token": (
            f"{run_date.isoformat()}:prime-big-deal-days:{market}:{article['slug']}"
        ),
        "return_to_top": True,
        "is_refresh": refreshing,
    }
    article["source_sha"] = (
        f"{run_date.isoformat()}-{topic[0]}-{market}-prime-big-deal-days-v1"
    )
    return article


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
        except Exception as exc:
            attempted.append({
                "topic": key,
                "status": "build-error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"[prime-warning] {market.upper()} {key}: {type(exc).__name__}: {exc}")
            continue

        if not article.get("_generator", {}).get("live_ebay_picks"):
            attempted.append({"topic": key, "status": "insufficient-live-listings"})
            print(
                f"[prime-warning] {market.upper()} {key}: "
                "not enough verified live listings; trying another category"
            )
            continue

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
            f"({row['pick_count']} live eBay picks)"
        )
        return row

    print(
        f"[prime-warning] {market.upper()}: no remaining candidate produced "
        "enough verified live listings"
    )
    return None


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
        changed = 0
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
