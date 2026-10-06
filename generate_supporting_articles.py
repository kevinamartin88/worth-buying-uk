from __future__ import annotations

from src.us_targeting import us_article_output

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import generate_daily_articles as daily
from src.search_console import rank_topics_by_search_console


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "authority_support.json"
LONDON = ZoneInfo("Europe/London")
ANGLES = ("budget", "refurbished", "value")
REFURBISHED_TOPICS = {
    "air-fryers", "large-capacity-air-fryers", "coffee-machines",
    "food-processors", "blenders", "stand-mixers", "cordless-vacuums",
    "robot-vacuums", "dehumidifiers", "air-purifiers", "carpet-cleaners",
    "steam-mops", "tvs", "soundbars", "tablets", "smartwatches",
    "dash-cams", "pressure-washers", "cordless-drills", "lawn-mowers",
}


class InsufficientSupportListings(ValueError):
    pass


def support_angle(base_key: str, iso_week: int) -> str:
    angle = ANGLES[(iso_week - 1) % len(ANGLES)]
    return "value" if angle == "refurbished" and base_key not in REFURBISHED_TOPICS else angle


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def rotation_topic_for_week(iso_week: int, market: str) -> tuple:
    clusters = list(daily.AUTHORITY_CLUSTERS.items())
    offset = 0 if market == "uk" else 1
    cluster_index = (iso_week - 1 + offset) % len(clusters)
    _, keys = clusters[cluster_index]

    cycle = (iso_week - 1) // len(clusters)
    key = keys[cycle % len(keys)]
    return next(topic for topic in daily.TOPICS if topic[0] == key)


def base_topic_for_week(iso_week: int, market: str) -> tuple:
    """Use GSC only to exploit proven site visibility, never as market-demand data."""
    authority_topics = [
        topic for topic in daily.TOPICS
        if topic[0] in daily.AUTHORITY_CORE_KEYS
    ]
    ranked = rank_topics_by_search_console(authority_topics, market)
    if ranked:
        topic, signal = ranked[0]
        score = float(signal.get("score") or 0)
        impressions = float(signal.get("impressions") or 0)
        position = float(signal.get("position") or 0)
        if score >= 55 and impressions >= 10 and 3 <= position <= 35:
            print(
                f"[support-gsc-opportunity] {market.upper()}: {topic[1]} "
                f"matched '{signal.get('query')}' "
                f"(score={score:.2f}, impressions={impressions:.0f}, "
                f"position={position:.1f})"
            )
            return topic

    topic = rotation_topic_for_week(iso_week, market)
    print(
        f"[support-rotation] {market.upper()}: {topic[1]} "
        "(no strong Search Console opportunity; using authority rotation)"
    )
    return topic


def support_topic(base: tuple, market: str, iso_week: int) -> tuple:
    key, display, query, max_uk, max_us, category, kicker = daily.localise_topic(base, market)
    angle = support_angle(base[0], iso_week)
    region_symbol = "£" if market == "uk" else "$"
    ceiling = float(max_uk if market == "uk" else max_us)

    if angle == "budget":
        budget = max(30, int(round((ceiling * 0.45) / 10.0) * 10))
        return (
            f"{key}-under-{budget}",
            f"{display} Under {region_symbol}{budget}",
            query,
            budget,
            budget,
            category,
            f"{display.upper()} VALUE GUIDE"[:38],
        )

    if angle == "refurbished":
        return (
            f"refurbished-{key}",
            f"Refurbished {display}",
            f"refurbished {query}",
            max_uk,
            max_us,
            category,
            "REFURBISHED VALUE GUIDE",
        )

    value_uk = max(30, int(round((float(max_uk) * 0.70) / 10.0) * 10))
    value_us = max(30, int(round((float(max_us) * 0.70) / 10.0) * 10))
    return (
        f"value-{key}",
        f"Value {display}",
        query,
        value_uk,
        value_us,
        category,
        f"{display.upper()} VALUE GUIDE"[:38],
    )


def _pillar_url(base_key: str, market: str, year: int) -> str:
    state_path = ROOT / "state" / (
        "articles_published.json" if market == "uk" else "articles_us_published.json"
    )
    article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
    state = _load_json(state_path)

    for slug, published in state.items():
        if not isinstance(published, dict) or published.get("status") != "published":
            continue
        source_file = str(published.get("source_file") or f"{slug}.json")
        article = _load_json(article_dir / source_file)
        generator = article.get("_generator") or {}
        if str(generator.get("topic") or "") != base_key:
            continue
        if str(generator.get("content_type") or "") == "authority-support":
            continue
        url = str(published.get("url") or "")
        if url:
            return url
    return ""


@us_article_output
def build_support_article(base: tuple, market: str, year: int, iso_week: int) -> dict:
    topic = support_topic(base, market, iso_week)
    article = daily.build_article(topic, market, year)
    if not article.get("_generator", {}).get("live_ebay_picks"):
        raise InsufficientSupportListings("too few verified listings for a supporting guide")

    base_key = base[0]
    cluster = daily.authority_cluster_for_topic(base_key)
    angle = support_angle(base_key, iso_week)
    pillar = _pillar_url(base_key, market, year)

    if pillar:
        bridge = (
            '<p style="border-left:4px solid #082f5b;padding-left:14px">'
            '<strong>Start with the main guide:</strong> '
            f'<a href="{pillar}">see our complete {base[1]} buying guide</a>. '
            'This supporting page focuses on a narrower buying question.</p>\n'
        )
        article["content_html"] = bridge + article["content_html"]

    article["_seo"]["authority_cluster"] = cluster
    article["_seo"]["supporting_content"] = True
    article["_seo"]["support_angle"] = angle
    article["_seo"]["pillar_topic"] = base_key
    article["_monetisation"]["authority_cluster"] = cluster
    article["_monetisation"]["supporting_money_page"] = True
    article["_generator"]["parent_topic"] = base_key
    article["_generator"]["content_type"] = "authority-support"
    article["_generator"]["support_angle"] = angle
    return article


def main() -> None:
    now = datetime.now(LONDON)
    iso = now.isocalendar()
    year = now.year
    week_key = f"{iso.year}-W{iso.week:02d}"
    state = _load_json(STATE_PATH)
    created = 0

    for market in ("uk", "us"):
        if str((state.get(market) or {}).get("week") or "") == week_key:
            print(f"[support-skip] {market.upper()}: {week_key} already generated")
            continue

        base = base_topic_for_week(iso.week, market)
        try:
            article = build_support_article(base, market, year, iso.week)
        except InsufficientSupportListings as exc:
            print(f"[support-skip] {market.upper()}: {exc}")
            continue
        article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
        article_dir.mkdir(parents=True, exist_ok=True)
        target = article_dir / f"{article['slug']}.json"

        refreshing = target.exists()
        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state[market] = {
            "week": week_key,
            "slug": article["slug"],
            "title": article["title"],
            "parent_topic": base[0],
            "authority_cluster": article["_seo"]["authority_cluster"],
            "support_angle": article["_seo"]["support_angle"],
            "selection_basis": "gsc-opportunity-or-authority-rotation",
            "action": "refreshed" if refreshing else "created",
        }
        created += 1
        print(
            f"[support-{state[market]['action']}] {market.upper()}: "
            f"{target.relative_to(ROOT)} "
            f"({article['_seo']['authority_cluster']} / {article['_seo']['support_angle']})"
        )

    _save_json(STATE_PATH, state)
    print(f"Authority support generation complete: {created} article(s).")


if __name__ == "__main__":
    main()
