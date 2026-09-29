from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from publish_articles_us import resolve_usa_blog
from src.blogger import BloggerClient


def client_with_service(blog_id: str = "123") -> tuple[BloggerClient, MagicMock]:
    service = MagicMock()
    return BloggerClient(service=service, blog_id=blog_id), service


def test_resolve_blog_accepts_custom_domain_and_confirms_admin() -> None:
    client, service = client_with_service()
    service.blogs.return_value.listByUser.return_value.execute.return_value = {
        "items": [
            {
                "id": "123",
                "name": "Worth Buying USA",
                "url": "https://www.worthbuyingusa.com/",
            }
        ]
    }
    service.blogUserInfos.return_value.get.return_value.execute.return_value = {
        "blog_user_info": {"hasAdminAccess": True}
    }

    resolve_usa_blog(client)

    assert client.blog_id == "123"
    service.blogUserInfos.return_value.get.assert_called_once_with(
        userId="self", blogId="123"
    )


def test_resolve_blog_rejects_wrong_numeric_secret() -> None:
    client, service = client_with_service(blog_id="wrong")
    service.blogs.return_value.listByUser.return_value.execute.return_value = {
        "items": [
            {
                "id": "123",
                "name": "Worth Buying UK",
                "url": "https://www.worthbuyinguk.co.uk/",
            }
        ]
    }

    with pytest.raises(RuntimeError, match="blog ID secret does not match"):
        client.resolve_blog(
            {"www.worthbuyinguk.co.uk", "worthbuyinguk.blogspot.com"},
            "Worth Buying UK",
        )


def test_create_live_post_stages_draft_then_publishes() -> None:
    client, service = client_with_service()
    posts = service.posts.return_value
    posts.insert.return_value.execute.return_value = {"id": "post-1", "status": "DRAFT"}
    posts.publish.return_value.execute.return_value = {
        "id": "post-1",
        "status": "LIVE",
        "url": "https://example.com/post",
    }

    result = client.create_post("Title", "<p>Body</p>", ["Buying Guide"])

    posts.insert.assert_called_once_with(
        blogId="123",
        body={"title": "Title", "content": "<p>Body</p>", "labels": ["Buying Guide"]},
        isDraft=True,
    )
    posts.publish.assert_called_once_with(blogId="123", postId="post-1")
    assert result["status"] == "LIVE"


def test_create_draft_does_not_publish() -> None:
    client, service = client_with_service()
    posts = service.posts.return_value
    posts.insert.return_value.execute.return_value = {"id": "post-1", "status": "DRAFT"}

    result = client.create_post("Title", "Body", is_draft=True)

    assert result["status"] == "DRAFT"
    posts.publish.assert_not_called()


def test_find_post_reuses_matching_draft() -> None:
    client, service = client_with_service()
    posts = service.posts.return_value
    posts.search.return_value.execute.return_value = {"items": []}
    posts.list.return_value.execute.return_value = {
        "items": [{"id": "draft-1", "title": "Existing draft", "status": "DRAFT"}]
    }

    found = client.find_post_by_exact_title("Existing draft")

    assert found == {"id": "draft-1", "title": "Existing draft", "status": "DRAFT"}
    posts.list.assert_called_once_with(
        blogId="123", status="draft", fetchBodies=False, maxResults=50
    )
