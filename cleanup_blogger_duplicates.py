from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from src.blogger import API_RETRIES, BloggerClient


ROOT = Path(__file__).resolve().parent
STATE_PATHS = {
    "uk": ROOT / "state" / "articles_published.json",
    "us": ROOT / "state" / "articles_us_published.json",
}
SUFFIX_RE = re.compile(r"_(\d{6,})(?=\.html$)")


def clean_path(url: str) -> str:
    path = urlsplit(str(url or "")).path
    return SUFFIX_RE.sub("", path)


def has_numeric_suffix(url: str) -> bool:
    return bool(SUFFIX_RE.search(urlsplit(str(url or "")).path))


def list_live_posts(blogger: BloggerClient) -> list[dict]:
    posts: list[dict] = []
    token = None
    while True:
        request = blogger.service.posts().list(
            blogId=blogger.blog_id,
            status="LIVE",
            fetchBodies=False,
            maxResults=500,
            pageToken=token,
        )
        payload = request.execute(num_retries=API_RETRIES)
        posts.extend(payload.get("items") or [])
        token = payload.get("nextPageToken")
        if not token:
            break
    return posts


def duplicate_groups(posts: list[dict]) -> list[tuple[dict, list[dict]]]:
    clean: dict[str, list[dict]] = {}
    suffixed: dict[str, list[dict]] = {}

    for post in posts:
        url = str(post.get("url") or "").strip()
        title = str(post.get("title") or "").strip()
        if not url or not title:
            continue
        base = clean_path(url)
        target = suffixed if has_numeric_suffix(url) else clean
        target.setdefault(base, []).append(post)

    groups: list[tuple[dict, list[dict]]] = []
    for base, duplicates in suffixed.items():
        primaries = clean.get(base) or []
        if len(primaries) != 1:
            continue
        primary = primaries[0]
        title = str(primary.get("title") or "").strip()
        matched = [
            post for post in duplicates
            if str(post.get("title") or "").strip() == title
            and str(post.get("id") or "") != str(primary.get("id") or "")
        ]
        if matched:
            groups.append((primary, matched))
    return groups


def update_state(market: str, groups: list[tuple[dict, list[dict]]]) -> int:
    path = STATE_PATHS[market]
    if not path.exists():
        return 0

    state = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    by_base = {
        clean_path(str(primary.get("url") or "")): primary
        for primary, _duplicates in groups
    }

    for entry in state.values():
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "")
        base = clean_path(url)
        primary = by_base.get(base)
        if not primary:
            continue
        primary_url = str(primary.get("url") or "")
        primary_id = str(primary.get("id") or "")
        if not primary_url or not primary_id:
            continue
        if entry.get("url") != primary_url or str(entry.get("post_id") or "") != primary_id:
            entry["url"] = primary_url
            entry["post_id"] = primary_id
            entry["status"] = "published"
            changed += 1

    if changed:
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return changed


def run(market: str, apply: bool) -> int:
    blogger = BloggerClient.from_env()
    posts = list_live_posts(blogger)
    groups = duplicate_groups(posts)

    if not groups:
        print(f"[duplicate-cleanup] {market.upper()}: no safe numeric-suffix duplicate groups found")
        return 0

    duplicate_count = 0
    for primary, duplicates in groups:
        print(
            f"[duplicate-cleanup] {market.upper()} primary: "
            f"{primary.get('title')} -> {primary.get('url')} ({primary.get('id')})"
        )
        for duplicate in duplicates:
            duplicate_count += 1
            print(
                f"[duplicate-cleanup] {market.upper()} duplicate: "
                f"{duplicate.get('url')} ({duplicate.get('id')})"
            )
            if apply:
                (
                    blogger.service.posts()
                    .revert(blogId=blogger.blog_id, postId=str(duplicate["id"]))
                    .execute(num_retries=API_RETRIES)
                )
                print(f"[duplicate-cleanup] reverted duplicate {duplicate['id']} to draft")

    if apply:
        repaired = update_state(market, groups)
        print(
            f"[duplicate-cleanup] {market.upper()}: reverted {duplicate_count} duplicate(s); "
            f"repaired {repaired} publication-state entr{'y' if repaired == 1 else 'ies'}"
        )
    else:
        print(
            f"[duplicate-cleanup] {market.upper()}: dry run only; "
            f"would revert {duplicate_count} duplicate(s)"
        )

    return duplicate_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely revert numeric-suffix duplicate Blogger posts to draft."
    )
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually revert duplicates and repair publication state. Default is dry-run.",
    )
    args = parser.parse_args()
    run(args.market, args.apply)


if __name__ == "__main__":
    main()
