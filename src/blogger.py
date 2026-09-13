from __future__ import annotations

import os

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

    def create_post(self, title: str, content: str) -> dict:
        body = {"title": title, "content": content}
        return (
            self.service.posts()
            .insert(blogId=self.blog_id, body=body, isDraft=False)
            .execute()
        )

    def update_post(self, post_id: str, title: str, content: str) -> dict:
        body = {"title": title, "content": content}
        return (
            self.service.posts()
            .patch(blogId=self.blog_id, postId=post_id, body=body)
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
        return None
