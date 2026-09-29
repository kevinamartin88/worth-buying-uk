from __future__ import annotations

import os
from urllib.parse import urlsplit

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


BLOGGER_SCOPE = "https://www.googleapis.com/auth/blogger"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class BloggerClient:
    def __init__(self, service, blog_id: str):
        self.service = service
        self.blog_id = blog_id

    @classmethod
    def from_env(cls) -> "BloggerClient":
        required = {
            "BLOGGER_CLIENT_ID": os.getenv("BLOGGER_CLIENT_ID"),
            "BLOGGER_CLIENT_SECRET": os.getenv("BLOGGER_CLIENT_SECRET"),
            "BLOGGER_REFRESH_TOKEN": os.getenv("BLOGGER_REFRESH_TOKEN"),
            "BLOGGER_BLOG_ID": os.getenv("BLOGGER_BLOG_ID"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError("Missing Blogger environment variables: " + ", ".join(missing))

        creds = Credentials(
            token=None,
            refresh_token=required["BLOGGER_REFRESH_TOKEN"],
            token_uri=TOKEN_URI,
            client_id=required["BLOGGER_CLIENT_ID"],
            client_secret=required["BLOGGER_CLIENT_SECRET"],
            scopes=[BLOGGER_SCOPE],
        )
        service = build("blogger", "v3", credentials=creds, cache_discovery=False)
        return cls(service=service, blog_id=required["BLOGGER_BLOG_ID"])

    @staticmethod
    def _host(url: str) -> str:
        return urlsplit(url).netloc.casefold().split(":", 1)[0]

    def resolve_blog(self, expected_hosts: set[str], label: str) -> dict:
        """Resolve and validate a writable Blogger target from the OAuth account.

        Blogger returns the active custom domain in ``blog.url`` when one is
        configured, so matching only the historical blogspot.com address can
        reject the correct blog. The numeric secret is still checked to prevent
        publishing to the wrong property.
        """
        hosts = {host.casefold() for host in expected_hosts}
        blogs = (
            self.service.blogs()
            .listByUser(userId="self")
            .execute()
            .get("items", [])
        )

        matching = [
            blog
            for blog in blogs
            if self._host(str(blog.get("url", ""))) in hosts
        ]
        target = next(
            (blog for blog in matching if str(blog.get("id", "")) == self.blog_id),
            None,
        )
        if target is None and matching:
            visible_ids = {str(blog.get("id", "")) for blog in matching}
            raise RuntimeError(
                f"{label} blog ID secret does not match the visible {label} blog "
                f"({', '.join(sorted(visible_ids))})."
            )
        if target is None:
            available = ", ".join(
                f"{blog.get('name', 'Unnamed')} ({blog.get('url', 'no URL')})"
                for blog in blogs
            ) or "none"
            raise RuntimeError(
                f"The authenticated Google account cannot see {label}. "
                f"Blogs visible to this token: {available}."
            )

        self.blog_id = str(target["id"])
        info = (
            self.service.blogUserInfos()
            .get(userId="self", blogId=self.blog_id)
            .execute()
        )
        per_user = info.get("blog_user_info") or info.get("blogUserInfo") or {}
        if per_user.get("hasAdminAccess") is False:
            raise RuntimeError(f"The authenticated Google account is not an admin of {label}.")

        print(
            f"[blog] Using {target.get('name', label)} ({target.get('url', '')}); "
            f"admin_access={per_user.get('hasAdminAccess')}"
        )
        return target

    def create_post(
        self,
        title: str,
        content: str,
        labels: list[str] | None = None,
        is_draft: bool = False,
    ) -> dict:
        body = {"title": title, "content": content}
        if labels:
            body["labels"] = labels
        # Staging as a draft before publishing is more reliable than asking
        # Blogger to insert a fully live affiliate article in one operation.
        # It also gives retries a clear post ID if the final publish call fails.
        post = (
            self.service.posts()
            .insert(blogId=self.blog_id, body=body, isDraft=True)
            .execute()
        )
        if is_draft:
            return post
        return self.publish_post(str(post["id"]))

    def update_post(
        self,
        post_id: str,
        title: str,
        content: str,
        labels: list[str] | None = None,
    ) -> dict:
        body = {"title": title, "content": content}
        if labels:
            body["labels"] = labels
        return (
            self.service.posts()
            .patch(blogId=self.blog_id, postId=post_id, body=body)
            .execute()
        )

    def get_post(self, post_id: str) -> dict:
        return (
            self.service.posts()
            .get(blogId=self.blog_id, postId=post_id)
            .execute()
        )

    def publish_post(self, post_id: str) -> dict:
        return (
            self.service.posts()
            .publish(blogId=self.blog_id, postId=post_id)
            .execute()
        )

    def find_post_by_exact_title(self, title: str):
        # Blogger search can be broader than an exact-title lookup, so verify the title.
        result = (
            self.service.posts()
            .search(blogId=self.blog_id, q=title, fetchBodies=False)
            .execute()
        )
        for post in result.get("items", []):
            if post.get("title") == title:
                return post

        # A prior run may have inserted the draft successfully but failed while
        # publishing it. Reuse that draft rather than creating a duplicate.
        drafts = (
            self.service.posts()
            .list(
                blogId=self.blog_id,
                status="draft",
                fetchBodies=False,
                maxResults=50,
            )
            .execute()
        )
        for post in drafts.get("items", []):
            if post.get("title") == title:
                return post
        return None
