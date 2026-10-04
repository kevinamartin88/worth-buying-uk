from __future__ import annotations

# Authority hub publisher trigger.

import argparse
import json
from datetime import datetime, timezone

from googleapiclient.errors import HttpError

from src.blogger import BloggerClient
from src.site_pages import MARKET, build_pages


EXPECTED_HOSTS = {
    "uk": {
        "www.worthbuyinguk.co.uk",
        "worthbuyinguk.co.uk",
        "worthbuyinguk.blogspot.com",
    },
    "us": {
        "www.worthbuyingusa.com",
        "worthbuyingusa.com",
        "worthbuyingusa.blogspot.com",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh WorthBuying authority hub pages")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    args = parser.parse_args()

    market = args.market
    client = BloggerClient.from_env()
    client.resolve_blog(EXPECTED_HOSTS[market], MARKET[market]["site"])

    page_state: dict[str, dict] = {}
    for page in build_pages(market):
        content_type = "page"
        try:
            result = client.upsert_page(page["title"], page["content"])
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 403:
                raise
            # Keep authority content live even if a particular Blogger account
            # temporarily refuses Page writes.
            result = client.upsert_post(
                page["title"],
                page["content"],
                labels=["Worth Buying", "Site Guides"],
            )
            content_type = "post"

        page_state[page["key"]] = {
            "id": str(result.get("id") or ""),
            "title": page["title"],
            "url": str(result.get("url") or ""),
            "content_type": content_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        print(
            f"[authority-page] {market.upper()} {page['title']} -> "
            f"{result.get('url') or result.get('id')}"
        )

    path = MARKET[market]["page_state"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(page_state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[authority-pages-complete] {market.upper()}: {len(page_state)} page(s)")


if __name__ == "__main__":
    main()
