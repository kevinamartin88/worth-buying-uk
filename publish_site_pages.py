from __future__ import annotations

# Authority hub publisher trigger.

import argparse
import json
from datetime import datetime, timezone

from googleapiclient.errors import HttpError

from src.blogger import BloggerClient
from src.internal_links import related_graph, update_discovery_links
from src.site_pages import MARKET, build_pages, load_catalog


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

    # Strengthen internal linking immediately instead of waiting for every
    # evergreen money page to reach its next refresh cycle. Only append links;
    # preserve the existing article body and affiliate URLs exactly as stored.
    published_state_path = (
        MARKET[market]["published"]
    )
    try:
        published_state = json.loads(
            published_state_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        published_state = {}

    catalog = load_catalog(market)
    graph = related_graph(catalog)
    backfilled = 0
    for row in catalog:
        slug = row["slug"]
        post_id = str((published_state.get(slug) or {}).get("post_id") or "")
        if not post_id:
            continue
        post = client.get_post_or_none(post_id)
        if not post or str(post.get("status") or "").upper() != "LIVE":
            continue
        content = str(post.get("content") or "")
        updated = update_discovery_links(content, row, graph[slug], page_state)
        if updated == content:
            continue
        client.update_post_content(post_id, updated)
        stored = client.get_post(post_id)
        if updated != str(stored.get("content") or ""):
            raise RuntimeError(f"Blogger did not retain discovery links for {slug}")
        backfilled += 1

    print(f"[authority-backfill] {market.upper()}: updated {backfilled} article(s)")

    path = MARKET[market]["page_state"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(page_state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[authority-pages-complete] {market.upper()}: {len(page_state)} page(s)")


if __name__ == "__main__":
    main()
