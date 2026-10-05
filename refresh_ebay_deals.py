from __future__ import annotations

import argparse
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    if mode == "validate":
        if not existing:
            raise RuntimeError("Weekly roundup is missing; run discovery first")
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
    print(f"[ebay-deals] {market}: {len(deals)} verified offers -> {result.get('url', result.get('id'))}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Refresh live UK or USA eBay Deals roundup")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument("--mode", choices=("discover", "validate"), default="discover")
    args = parser.parse_args()
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"), respect_retry_after_header=True,
    )))
    ebay = EbayClient.for_market(args.market, campaign_id=TRACKING[args.market]["campid"], session=session)
    if ebay.env != "production":
        raise RuntimeError("Live Deals refresh requires EBAY_ENV=production")
    refresh(args.market, args.mode, ebay, BloggerClient.from_env(), datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
