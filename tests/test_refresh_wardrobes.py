from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.rakuten import RakutenProduct
import refresh_wardrobe_roundup as repair


def product(name, price="499.00", currency="GBP"):
    return RakutenProduct(name=name, merchant="Choice Furniture Superstore", url="https://click.linksynergy.com/link?murl=" + name.replace(" ", "-"), price=price, currency=currency)


def original():
    return {"slug": repair.SLUG, "title": "Current Wardrobes Offers from Approved UK Retailers (October 2026)", "_generator": {"market": "uk"}}


def test_refresh_uses_complete_wardrobes_and_keeps_original_identity():
    client = Mock()
    client.search.return_value = [
        product("Wardrobe Hangers", "199.00"), product("Wardrobe hanging rail", "129.00"),
        product("Oak 2 Door Wardrobe"), product("White 3 Door Wardrobe"), product("Mirrored Sliding Wardrobe"),
        product("US 4 Door Wardrobe", currency="USD"),
    ]
    client.validate_product_destination.return_value = (True, "ok", "https://retailer/product")
    article = repair.refreshed_article(original(), client, datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert article["slug"] == repair.SLUG and article["title"] == original()["title"]
    assert article["_generator"]["offer_count"] == 3
    assert "Wardrobe Hangers" not in article["content_html"]
    assert "hanging rail" not in article["content_html"]
    assert "US 4 Door" not in article["content_html"]
    assert client.validate_product_destination.call_count == 3


def test_inadequate_feed_never_replaces_article():
    client = Mock()
    client.search.return_value = [product("Wardrobe Hangers", "199.00")]
    with pytest.raises(RuntimeError, match="Fewer than three"):
        repair.refreshed_article(original(), client, datetime.now(timezone.utc))


def test_wrong_article_cannot_be_repaired():
    with pytest.raises(ValueError, match="restricted"):
        repair.refreshed_article({"slug": "another-post"}, Mock(), datetime.now(timezone.utc))


def test_existing_post_body_is_updated_and_verified_without_duplicate(monkeypatch):
    article = original() | {"content_html": "<p>Complete wardrobes</p>", "_generator": {"offer_count": 3}}
    monkeypatch.setattr(repair, "add_required_hero", lambda *args: ('<img src="hero.jpg">' + args[0], "hero.jpg"))
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = {"id": "42"}
    url = "https://www.worthbuyinguk.co.uk/2026/10/existing.html"
    blogger.get_post_or_none.side_effect = lambda post_id: {"url": url, "content": blogger.update_post_content.call_args.args[1] if blogger.update_post_content.called else "old"}
    repair.publish_existing(article, blogger)
    blogger.update_post_content.assert_called_once()
    blogger.create_post.assert_not_called()
    blogger.upsert_post.assert_not_called()


def test_missing_original_post_is_not_recreated():
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = None
    with pytest.raises(RuntimeError, match="refusing to create"):
        repair.publish_existing(original(), blogger)
    blogger.update_post_content.assert_not_called()
