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
        blogId="123", status="DRAFT", fetchBodies=False, maxResults=50
    )


def test_upsert_page_updates_existing_permanent_page() -> None:
    client, service = client_with_service()
    pages = service.pages.return_value
    pages.list.return_value.execute.return_value = {
        "items": [{"id": "page-1", "title": "Discount Codes"}]
    }
    pages.patch.return_value.execute.return_value = {
        "id": "page-1",
        "title": "Discount Codes",
        "url": "https://example.com/p/discount-codes.html",
    }

    result = client.upsert_page("Discount Codes", "<p>Fresh codes</p>")

    pages.patch.assert_called_once_with(
        blogId="123",
        pageId="page-1",
        body={"title": "Discount Codes", "content": "<p>Fresh codes</p>"},
    )
    pages.insert.assert_not_called()
    assert result["id"] == "page-1"


def test_upsert_page_creates_page_when_missing() -> None:
    client, service = client_with_service()
    pages = service.pages.return_value
    pages.list.return_value.execute.return_value = {"items": []}
    pages.insert.return_value.execute.return_value = {"id": "page-2", "title": "Discount Codes"}

    client.upsert_page("Discount Codes", "<p>Codes</p>")

    pages.insert.assert_called_once_with(
        blogId="123",
        body={"title": "Discount Codes", "content": "<p>Codes</p>"},
        isDraft=False,
    )


def test_upsert_post_updates_existing_live_fallback() -> None:
    client, _service = client_with_service()
    client.find_post_by_exact_title = MagicMock(
        return_value={"id": "post-1", "title": "Discount Codes", "status": "LIVE"}
    )
    client.update_post = MagicMock(
        return_value={"id": "post-1", "status": "LIVE", "url": "https://example.com/codes"}
    )
    client.publish_post = MagicMock()

    result = client.upsert_post("Discount Codes", "<p>Fresh</p>", ["Discount Codes", "Deals"])

    client.update_post.assert_called_once_with(
        "post-1", "Discount Codes", "<p>Fresh</p>", labels=["Discount Codes", "Deals"]
    )
    client.publish_post.assert_not_called()
    assert result["status"] == "LIVE"


def test_get_post_can_verify_unpublished_draft():
    client, service = client_with_service()
    draft = {"id": "draft-1", "status": "DRAFT", "content": "<p>Held for review</p>"}
    def get_post(**kwargs):
        if kwargs.get("view") != "ADMIN":
            raise RuntimeError("Draft is not available through reader view")
        response = MagicMock()
        response.execute.return_value = draft
        return response
    service.posts.return_value.get.side_effect = get_post
    assert client.get_post("draft-1") == draft
