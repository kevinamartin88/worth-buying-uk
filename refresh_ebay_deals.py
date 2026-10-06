from __future__ import annotations

import argparse
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.article_images import backfill_hero_if_missing, require_hero_image, verify_required_hero
from src.blogger import BloggerClient
from src.ebay import EbayClient
from src.ebay_deals import TITLES, TRACKING, discover, revalidate, render

EXPECTED_HOSTS = {
    "uk": {"www.worthbuyinguk.co.uk", "worthbuyinguk.co.uk", "worthbuyinguk.blogspot.com"},
    "us": {"www.worthbuyingusa.com", "worthbuyingusa.com", "worthbuyingusa.blogspot.com"},
}


def refresh(market, mode, ebay, blogger, now):
    blogger.resolve_blog(EXPECTED_HOSTS[market], TITLES[market])
    existing = blogger.find_post_by_exact_title(TITLES[market])
    if mode == "repair-images":
        if not existing:
            print(f"[ebay-deals-skip] {market}: no existing roundup to repair")
            return None
        post_id = str(existing["id"])
        post = blogger.get_post_or_none(post_id)
        if not post or not isinstance(post.get("content"), str):
            raise RuntimeError("Weekly roundup could not be read; image repair aborted")
        # Only patch the body: retain current offers, metadata, title, labels and date.
        content, hero_url, changed = backfill_hero_if_missing(
            post["content"], market, f"weekly-ebay-deals-{market}", TITLES[market]
        )
        result = blogger.update_post_content(post_id, content) if changed else post
        stored = blogger.get_post_or_none(post_id)
        if not stored:
            raise RuntimeError("Weekly roundup could not be read after image repair")
        verify_required_hero(stored.get("content", ""), hero_url, TITLES[market])
        print(f"[ebay-deals-image] {market}: {'repaired' if changed else 'already present'}")
        return result
    if mode == "validate":
        if not existing:
            print(
                f"[ebay-deals-skip] {market}: weekly roundup does not exist yet; "
                "validation will resume after the next discovery run"
            )
            return None
        # Post search may omit bodies; fetch the authoritative current content.
        post = blogger.get_post_or_none(str(existing["id"]))
        if not post:
            raise RuntimeError("Weekly roundup could not be read")
        deals, discovered_at = revalidate(ebay, market, post["content"], now)
    else:
        deals = discover(ebay, market, now)
        discovered_at = now.isoformat()
    content = render(deals, market, now, discovered_at)
    # The live Deals menus use /search?q=Deals. Title + label place this stable
    # roundup in that existing section, without changing the menu or page URL.
    result = blogger.upsert_post(TITLES[market], content, labels=["Deals", "eBay", "Weekly Deals"])
    stored = blogger.get_post_or_none(str(result["id"]))
    if not stored:
        raise RuntimeError("Weekly roundup could not be read after publishing")
    verify_required_hero(
        stored.get("content", ""), require_hero_image(market, f"weekly-ebay-deals-{market}"), TITLES[market]
    )
    print(f"[ebay-deals] {market}: {len(deals)} verified offers -> {result.get('url', result.get('id'))}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Refresh live UK or USA eBay Deals roundup")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument("--mode", choices=("discover", "validate", "repair-images"), default="discover")
    args = parser.parse_args()
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"), respect_retry_after_header=True,
    )))
    ebay = None if args.mode == "repair-images" else EbayClient.for_market(
        args.market, campaign_id=TRACKING[args.market]["campid"], session=session
    )
    if ebay is not None and ebay.env != "production":
        raise RuntimeError("Live Deals refresh requires EBAY_ENV=production")
    refresh(args.market, args.mode, ebay, BloggerClient.from_env(), datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
