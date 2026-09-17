from __future__ import annotations

import os

from src.ebay import EbayClient


def main() -> None:
    if os.getenv("EBAY_ENV", "").strip().lower() != "production":
        raise SystemExit("Refusing live check unless EBAY_ENV=production")
    if not os.getenv("EPN_CAMPAIGN_ID", "").strip():
        raise SystemExit("Missing EPN_CAMPAIGN_ID; affiliate tracking was not tested")

    client = EbayClient.for_market("uk")
    items = client.search(
        query="air fryers",
        max_price=500,
        require_free_shipping=False,
        affiliate_reference="live-test-uk-air-fryers",
        limit=3,
    )
    if not items:
        raise SystemExit("Browse search authenticated but returned no UK air fryer listings")

    item_id = items[0].get("itemId")
    if not item_id:
        raise SystemExit("Browse search returned a listing without an itemId")
    detail = client.get_item(item_id, affiliate_reference="live-test-uk-air-fryers")
    if detail.get("itemId") != item_id:
        raise SystemExit("getItem response did not match the searched item")
    if not detail.get("itemAffiliateWebUrl"):
        raise SystemExit("getItem succeeded but no EPN affiliate URL was returned")

    # Print validation signals only: never tokens, credentials, URLs, seller
    # details, listing titles, or full API responses.
    print("Production OAuth client-credentials flow: OK")
    print(f"Browse search (EBAY_GB, air fryers): OK ({len(items)} listing(s))")
    print("Browse getItem: OK")
    print("EPN affiliate URL: OK")


if __name__ == "__main__":
    main()
