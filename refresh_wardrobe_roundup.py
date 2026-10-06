"""Refresh the existing UK wardrobe roundup from approved live retailer feeds."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from generate_rakuten_articles import (
    MAX_PRODUCTS, MIN_PRODUCTS, RAKUTEN_TOPICS, build_article,
    relevant_products, validated_products,
)
from src.article_copy import clean_article_disclosures
from src.article_images import add_required_hero, verify_required_hero
from src.blogger import BloggerClient
from src.rakuten import RakutenClient
from publish_articles import UK_BLOG_HOSTS

ROOT = Path(__file__).resolve().parent
SLUG = "approved-retailer-wardrobes-uk-2026-10-05"
SEARCHES = ("2 door wardrobe", "3 door wardrobe", "4 door wardrobe", "sliding wardrobe", "armoire")
ACCESSORIES = re.compile(
    r"\b(hangers?|rails?|organisers?|organizers?|inserts?|tracks?|runners?|hinges?|"
    r"handles?|brackets?|fittings?|spares?|replacements?|dampers?|shelves|shelf|"
    r"panels?|locks?|castors?|casters?|accessor(?:y|ies))\b", re.I
)
FOR_WARDROBE = re.compile(r"\bfor\b.*\b(?:wardrobes?|armoires?)\b", re.I)


def refreshed_article(original, client, now):
    if original.get("slug") != SLUG or original.get("_generator", {}).get("market") != "uk":
        raise ValueError("Repair is restricted to the existing UK wardrobe roundup")
    candidates, seen = [], set()
    for query in SEARCHES:
        for product in relevant_products(client.search(query, limit=20), "wardrobe armoire", "wardrobes"):
            if (product.url in seen or ACCESSORIES.search(product.name)
                    or FOR_WARDROBE.search(product.name) or product.currency != "GBP"):
                continue
            seen.add(product.url)
            candidates.append(product)
    products = validated_products(client, candidates, "uk")[:MAX_PRODUCTS]
    if len(products) < MIN_PRODUCTS:
        raise RuntimeError("Fewer than three complete wardrobes with validated retailer links; no article changed")
    topic = next(row for row in RAKUTEN_TOPICS if row[0] == "wardrobes")
    result = build_article(topic, products, "uk", now)
    # Refresh the original asset rather than publishing a second date-based roundup.
    result["slug"] = original["slug"]
    result["title"] = original["title"]
    result["pinterest_title"] = original["title"]
    result["source_sha"] = f"{now.isoformat()}-wardrobes-uk-complete-products-v1"
    result["_generator"]["refreshed_at"] = now.isoformat()
    return result


def publish_existing(article, blogger):
    blogger.resolve_blog(UK_BLOG_HOSTS, "Worth Buying UK")
    existing = blogger.find_post_by_exact_title(article["title"])
    if not existing:
        raise RuntimeError("Original wardrobe post not found; refusing to create a duplicate")
    post_id = str(existing["id"])
    before = blogger.get_post_or_none(post_id)
    if not before or not before.get("url"):
        raise RuntimeError("Original wardrobe post could not be read")
    content, hero_url = add_required_hero(
        clean_article_disclosures(article["content_html"]), "uk", SLUG, article["title"]
    )
    blogger.update_post_content(post_id, content)
    stored = blogger.get_post_or_none(post_id)
    if not stored or stored.get("url") != before["url"]:
        raise RuntimeError("Wardrobe repair did not preserve the original permalink")
    verify_required_hero(stored.get("content", ""), hero_url, article["title"])
    if stored.get("content") != content:
        raise RuntimeError("Blogger did not retain the refreshed wardrobe offers")
    print(f"[wardrobes-repaired] {article['_generator']['offer_count']} complete wardrobes: {stored['url']}")


def main():
    path = ROOT / "articles" / f"{SLUG}.json"
    client = RakutenClient.for_market("uk")
    if client is None:
        raise RuntimeError("Approved UK retailer feed credentials are required")
    article = refreshed_article(json.loads(path.read_text(encoding="utf-8")), client, datetime.now(timezone.utc))
    publish_existing(article, BloggerClient.from_env())
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
