from io import BytesIO

import pytest
from PIL import Image

from src import product_image_quality as quality


def test_large_variant_is_verified_and_keeps_same_listing(monkeypatch):
    seen = []
    def dimensions(url):
        seen.append(url)
        return 1200, 900
    monkeypatch.setattr(quality, "image_dimensions", dimensions)
    url, width, height = quality.checked_product_image("https://i.ebayimg.com/images/g/product/s-l225.jpg")
    assert url == "https://i.ebayimg.com/images/g/product/s-l1600.jpg"
    assert seen == [url]
    assert (width, height) == (1200, 900)


def test_missing_large_variant_falls_back_to_adequate_original(monkeypatch):
    def dimensions(url):
        if "s-l1600" in url:
            raise OSError("missing")
        return 800, 600
    monkeypatch.setattr(quality, "image_dimensions", dimensions)
    original = "https://i.ebayimg.com/images/g/product/s-l800.jpg"
    assert quality.checked_product_image(original)[0] == original


def test_tiny_photo_blocks_publication_instead_of_being_stretched(monkeypatch):
    monkeypatch.setattr(quality, "image_dimensions", lambda url: (225, 225))
    with pytest.raises(RuntimeError, match="Replace the image before publishing"):
        quality.prepare_product_images('<img src="https://i.ebayimg.com/images/g/a/s-l225.jpg">')


def test_portrait_and_landscape_photos_share_a_frame_and_keep_product_identity(monkeypatch):
    monkeypatch.setattr(quality, "image_dimensions", lambda url: (600, 1200) if "portrait" in url else (1200, 600))
    content = '<img src="https://i.ebayimg.com/images/g/portrait/s-l225.jpg" alt="Tall product"><img src="https://i.ebayimg.com/images/g/wide/s-l225.jpg" alt="Wide product"><img src="https://example.com/chart.png">'
    result = quality.prepare_product_images(content)
    assert result.count(quality.FRAME_STYLE) == 2
    assert result.count("object-fit:contain!important") == 2
    assert 'alt="Tall product"' in result and 'alt="Wide product"' in result
    assert '<img src="https://example.com/chart.png">' in result
    assert quality.prepare_product_images(result) == result


def test_corrupt_remote_image_is_rejected(monkeypatch):
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield b"not an image"
    monkeypatch.setattr(quality.requests, "get", lambda *a, **k: Response())
    quality.image_dimensions.cache_clear()
    with pytest.raises(OSError):
        quality.image_dimensions("https://i.ebayimg.com/images/g/corrupt/s-l1600.jpg")


def test_remote_image_is_fully_decoded(monkeypatch):
    out = BytesIO()
    Image.new("RGB", (800, 600), "white").save(out, format="JPEG")
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield out.getvalue()
    monkeypatch.setattr(quality.requests, "get", lambda *a, **k: Response())
    quality.image_dimensions.cache_clear()
    assert quality.image_dimensions("https://i.ebayimg.com/images/g/valid/s-l1600.jpg") == (800, 600)

