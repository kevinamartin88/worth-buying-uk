from __future__ import annotations

from src import article_images


def test_hero_image_url_uses_market_and_slug():
    assert article_images.hero_image_url("uk", "example-guide").endswith(
        "/assets/ai/uk/example-guide.jpg"
    )
    assert article_images.hero_image_url("us", "example-guide").endswith(
        "/assets/ai/us/example-guide.jpg"
    )


def test_image_detection():
    assert article_images.has_any_image('<p><img src="x.jpg" alt="x"></p>')
    assert not article_images.has_any_image("<p>No image</p>")


def test_add_required_hero_prepends_expected_image(monkeypatch):
    monkeypatch.setattr(
        article_images,
        "require_hero_image",
        lambda market, slug: f"https://images.example/{market}/{slug}.jpg",
    )
    content, image_url = article_images.add_required_hero(
        "<p>Article text</p>",
        "uk",
        "test-slug",
        "Test article",
    )
    assert image_url in content
    assert content.index("<img") < content.index("Article text")


def test_backfill_preserves_existing_image(monkeypatch):
    monkeypatch.setattr(
        article_images,
        "require_hero_image",
        lambda market, slug: f"https://images.example/{market}/{slug}.jpg",
    )
    original = '<p><img src="legacy.jpg" alt="legacy"></p><p>Body</p>'
    content, _, changed = article_images.backfill_hero_if_missing(
        original,
        "us",
        "test-slug",
        "Test article",
    )
    assert content == original
    assert changed is False
