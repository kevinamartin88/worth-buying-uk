from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


BLOGGER_SCOPE = "https://www.googleapis.com/auth/blogger"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalise_host(url: str) -> str:
    return urlsplit(url).netloc.casefold().split(":", 1)[0]


def verify_connection(market: str, expected_host: str, write_test: bool = False) -> None:
    prefix = "BLOGGER" if market == "uk" else "BLOGGER_US"
    client_id = required_env(f"{prefix}_CLIENT_ID")
    client_secret = required_env(f"{prefix}_CLIENT_SECRET")
    refresh_token = required_env(f"{prefix}_REFRESH_TOKEN")
    expected_blog_id = required_env(f"{prefix}_BLOG_ID")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[BLOGGER_SCOPE],
    )
    service = build("blogger", "v3", credentials=credentials, cache_discovery=False)
    blogs = service.blogs().listByUser(userId="self").execute().get("items", [])

    matching_blog = next(
        (blog for blog in blogs if normalise_host(str(blog.get("url", ""))) == expected_host),
        None,
    )
    if not matching_blog:
        visible_hosts = sorted(
            host
            for blog in blogs
            if (host := normalise_host(str(blog.get("url", ""))))
        )
        raise RuntimeError(
            f"{market.upper()} token cannot see {expected_host}. "
            f"Visible blog hosts: {', '.join(visible_hosts) or 'none'}"
        )

    actual_blog_id = str(matching_blog.get("id", ""))
    if actual_blog_id != expected_blog_id:
        raise RuntimeError(
            f"{market.upper()} blog ID secret does not match the {expected_host} blog."
        )

    user_info = (
        service.blogUserInfos()
        .get(userId="self", blogId=actual_blog_id)
        .execute()
    )
    per_blog = user_info.get("blog_user_info") or user_info.get("blogUserInfo") or {}
    has_admin_access = per_blog.get("hasAdminAccess")
    if has_admin_access is False:
        raise RuntimeError(f"{market.upper()} token does not have admin access to {expected_host}.")

    print(
        f"[ok] {market.upper()} Blogger OAuth connected to {expected_host}; "
        f"admin_access={has_admin_access}"
    )

    if write_test:
        title = (
            f"WorthBuying API write test {market.upper()} "
            f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )
        draft = (
            service.posts()
            .insert(
                blogId=actual_blog_id,
                body={
                    "title": title,
                    "content": "<p>Temporary automated Blogger API write test. Safe to delete.</p>",
                },
                isDraft=True,
            )
            .execute(num_retries=4)
        )
        post_id = str(draft["id"])
        print(f"[write-ok] {market.upper()} temporary draft created: {post_id}")
        service.posts().delete(blogId=actual_blog_id, postId=post_id).execute(num_retries=4)
        print(f"[delete-ok] {market.upper()} temporary draft deleted")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a Blogger OAuth token and blog target without creating or editing posts."
    )
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    parser.add_argument(
        "--write-test",
        action="store_true",
        help="Create and immediately delete a temporary Blogger draft to verify write access.",
    )
    args = parser.parse_args()

    expected_host = (
        "www.worthbuyinguk.co.uk"
        if args.market == "uk"
        else "www.worthbuyingusa.com"
    )
    verify_connection(args.market, expected_host, write_test=args.write_test)


if __name__ == "__main__":
    main()
