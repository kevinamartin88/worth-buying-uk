from __future__ import annotations

import os
from urllib.parse import urlsplit

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


BLOGGER_SCOPE = "https://www.googleapis.com/auth/blogger"
TOKEN_URI = "https://oauth2.googleapis.com/token"
API_RETRIES = 4


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
            .execute(num_retries=API_RETRIES)
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
            .execute(num_retries=API_RETRIES)
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
            .execute(num_retries=API_RETRIES)
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
            .execute(num_retries=API_RETRIES)
        )

    def update_post_content(self, post_id: str, content: str) -> dict:
        """Patch only a post body, preserving any manually edited title and labels."""
        return (
            self.service.posts()
            .patch(
                blogId=self.blog_id,
                postId=post_id,
                body={"content": content},
            )
            .execute(num_retries=API_RETRIES)
        )

    def get_post(self, post_id: str) -> dict:
        return (
            self.service.posts()
            .get(blogId=self.blog_id, postId=post_id, view="ADMIN")
            .execute(num_retries=API_RETRIES)
        )

    def get_post_or_none(self, post_id: str) -> dict | None:
        """Return a Blogger post, treating a stale/deleted post ID as absent."""
        try:
            return self.get_post(post_id)
        except HttpError as exc:
            if getattr(exc.resp, "status", None) == 404:
                print(f"[blogger-stale-id] Post {post_id} no longer exists; re-resolving by title.")
                return None
            raise

    def publish_post(self, post_id: str) -> dict:
        return (
            self.service.posts()
            .publish(blogId=self.blog_id, postId=post_id)
            .execute(num_retries=API_RETRIES)
        )

    def find_post_by_exact_title(self, title: str):
        # Blogger search can be broader than an exact-title lookup, so verify the title.
        result = (
            self.service.posts()
            .search(blogId=self.blog_id, q=title, fetchBodies=False)
            .execute(num_retries=API_RETRIES)
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
                status="DRAFT",
                fetchBodies=False,
                maxResults=50,
            )
            .execute(num_retries=API_RETRIES)
        )
        for post in drafts.get("items", []):
            if post.get("title") == title:
                return post
        return None

    def find_page_by_exact_title(self, title: str):
        result = (
            self.service.pages()
            .list(blogId=self.blog_id, fetchBodies=False, maxResults=500)
            .execute(num_retries=API_RETRIES)
        )
        return next(
            (page for page in result.get("items", []) if page.get("title") == title),
            None,
        )

    def upsert_page(self, title: str, content: str) -> dict:
        """Create a Blogger Page once, then refresh that same permanent Page."""
        existing = self.find_page_by_exact_title(title)
        body = {"title": title, "content": content}
        if existing:
            return (
                self.service.pages()
                .patch(
                    blogId=self.blog_id,
                    pageId=str(existing["id"]),
                    body=body,
                )
                .execute(num_retries=API_RETRIES)
            )
        return (
            self.service.pages()
            .insert(blogId=self.blog_id, body=body, isDraft=False)
            .execute(num_retries=API_RETRIES)
        )

    def upsert_post(
        self,
        title: str,
        content: str,
        labels: list[str] | None = None,
    ) -> dict:
        """Maintain one stable post when a Blogger account cannot create Pages."""
        existing = self.find_post_by_exact_title(title)
        if not existing:
            return self.create_post(title, content, labels=labels)
        result = self.update_post(str(existing["id"]), title, content, labels=labels)
        status = str(result.get("status") or existing.get("status") or "").casefold()
        if status == "draft":
            return self.publish_post(str(existing["id"]))
        return result
