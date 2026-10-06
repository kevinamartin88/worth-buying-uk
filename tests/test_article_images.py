from __future__ import annotations

from src import article_images


def test_hero_quality_gate_rejects_corrupt_or_small_images(tmp_path):
    import pytest
    from PIL import Image
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"not a jpeg")
    with pytest.raises(RuntimeError, match="invalid hero image"):
        article_images.validate_hero_file(broken)
    small = tmp_path / "small.jpg"
    Image.new("RGB", (225, 225)).save(small)
    with pytest.raises(RuntimeError, match="need at least 900x450"):
        article_images.validate_hero_file(small)
    valid = tmp_path / "valid.jpg"
    Image.new("RGB", (1600, 900)).save(valid)
    article_images.validate_hero_file(valid)


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


def test_backfill_requires_the_expected_article_image(monkeypatch):
    expected = "https://images.example/us/test-slug.jpg"
    monkeypatch.setattr(
        article_images,
        "require_hero_image",
        lambda market, slug: expected,
    )
    legacy = '<p><img src="legacy.jpg" alt="legacy"></p><p>Body</p>'
    content, image_url, changed = article_images.backfill_hero_if_missing(
        legacy,
        "us",
        "test-slug",
        "Test article",
    )
    assert changed is True
    assert image_url == expected
    assert expected in content
    assert content.index(expected) < content.index("legacy.jpg")


def test_backfill_preserves_expected_article_image(monkeypatch):
    expected = "https://images.example/us/test-slug.jpg"
    monkeypatch.setattr(
        article_images,
        "require_hero_image",
        lambda market, slug: expected,
    )
    original = f'<p><img src="{expected}" alt="hero"></p><p>Body</p>'
    content, image_url, changed = article_images.backfill_hero_if_missing(
        original,
        "us",
        "test-slug",
        "Test article",
    )
    assert content == original
    assert image_url == expected
    assert changed is False





def test_refreshed_hero_url_changes_when_image_bytes_change(monkeypatch, tmp_path):
    from PIL import Image
    monkeypatch.setattr(article_images, "ROOT", tmp_path)
    path = article_images.hero_image_path("us", "refreshed-guide")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 900), "white").save(path)
    path.with_suffix(".jpg.style").write_text(
        "worth-buying-hero-text-v1+updated-badge-v1-updated-on-6-october-2026",
        encoding="utf-8",
    )
    first = article_images.hero_image_url("us", "refreshed-guide")
    Image.new("RGB", (1600, 900), "black").save(path)
    second = article_images.hero_image_url("us", "refreshed-guide")
    assert "?v=" in first
    assert "?v=" in second
    assert first != second


def test_backfill_replaces_stale_hero_instead_of_duplicating(monkeypatch):
    expected = "https://images.example/us/test-slug.jpg?v=fresh"
    monkeypatch.setattr(
        article_images,
        "require_hero_image",
        lambda market, slug: expected,
    )
    old = (
        '<div class="wb-article-hero"><img src="https://images.example/us/test-slug.jpg"></div>'
        '<p>Body</p>'
    )
    content, image_url, changed = article_images.backfill_hero_if_missing(
        old,
        "us",
        "test-slug",
        "Test article",
    )
    assert changed is True
    assert image_url == expected
    assert expected in content
    assert content.count('class="wb-article-hero"') == 1
    assert "test-slug.jpg\"" not in content
