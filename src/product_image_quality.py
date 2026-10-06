"""Consistent, verified retailer photographs for article product cards."""
from __future__ import annotations

import html
import logging
import re
from functools import lru_cache
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image

DISPLAY_SIZE = 280
MIN_SOURCE_EDGE = DISPLAY_SIZE * 2
MAX_BYTES = 8 * 1024 * 1024
FRAME_STYLE = (
    "width:280px!important;max-width:100%!important;aspect-ratio:1/1;"
    "margin:0 auto 14px;display:flex;align-items:center;justify-content:center;"
    "background:#fff;overflow:hidden;"
)
IMAGE_STYLE = (
    "width:100%!important;height:100%!important;max-width:100%!important;"
    "max-height:100%!important;object-fit:contain!important;"
    "display:block;margin:0!important;border-radius:10px;"
)
LOG = logging.getLogger(__name__)


def is_ebay_image(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname == "i.ebayimg.com" and parsed.port in (None, 443)


def is_amazon_image(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {
            "m.media-amazon.com",
            "images-na.ssl-images-amazon.com",
            "images-eu.ssl-images-amazon.com",
        }
        and parsed.port in (None, 443)
    )


@lru_cache(maxsize=512)
def image_dimensions(url: str) -> tuple[int, int]:
    """Read bounded image bytes and decode the entire image, not just its header."""
    if not is_ebay_image(url):
        raise ValueError("Unsupported retailer image host")
    with requests.get(url, timeout=(5, 10), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Image did not return HTTP 200")
        payload = bytearray()
        for chunk in response.iter_content(65536):
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError("Retailer image exceeds 8 MB")
    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        image.load()
        return image.size


def checked_product_image(url: str) -> tuple[str, int, int]:
    """Try the same listing image at larger resolution; never swap products."""
    parts = urlsplit(url)
    larger_path = re.sub(r"/s-l\d+(?=\.[A-Za-z]+$)", "/s-l1600", parts.path)
    larger = urlunsplit(parts._replace(path=larger_path))
    errors = []
    for candidate in dict.fromkeys((larger, url)):
        try:
            width, height = image_dimensions(candidate)
            if max(width, height) < MIN_SOURCE_EDGE:
                raise ValueError(f"only {width}x{height}; need at least {MIN_SOURCE_EDGE}px on the long edge")
            if min(width, height) < 100:
                raise ValueError("image is too narrow to present a useful product photograph")
            LOG.info("[product-image-ok] %sx%s in %spx frame: %s", width, height, DISPLAY_SIZE, candidate)
            return candidate, width, height
        except (requests.RequestException, OSError, ValueError) as exc:
            errors.append(str(exc))
    raise RuntimeError(f"Product image quality check failed for {url}: {'; '.join(errors)}. Replace the image before publishing.")


def product_image_html(url: str, title: str) -> str:
    return (
        f'<div class="wb-product-image-frame" style="{FRAME_STYLE}">'
        f'<img class="wb-product-image" src="{html.escape(url, quote=True)}" '
        f'alt="{html.escape(title, quote=True)}" loading="lazy" decoding="async" '
        f'style="{IMAGE_STYLE}"></div>'
    )


class _ImageTag(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)


def prepare_product_images(content: str) -> str:
    """Gate actual eBay listing photos and standardise legacy and new cards."""
    content = re.sub(
        r'<div class="wb-product-image-frame"[^>]*>\s*(<img\b[^>]*>)\s*</div>',
        r'\1', content, flags=re.IGNORECASE,
    )
    def replace(match):
        parser = _ImageTag()
        parser.feed(match.group(0))
        attrs = parser.attrs
        url = attrs.get("src", "")
        if is_amazon_image(url):
            # Amazon Creators API images.primary.large is already the official
            # product image resource, so preserve it and standardise the card.
            return product_image_html(url, attrs.get("alt", "Product photograph"))
        if not is_ebay_image(url):
            if "wb-product-image" in (attrs.get("class") or "").split():
                raise RuntimeError(f"Product image quality check requires a supported retailer image: {url}")
            return match.group(0)
        checked_url, _, _ = checked_product_image(url)
        # A fixed square viewport gives every product the same visual allocation.
        # Contain preserves portrait/landscape product shapes without cropping.
        return product_image_html(checked_url, attrs.get("alt", "Product photograph"))

    return re.sub(r"<img\b[^>]*>", replace, content, flags=re.IGNORECASE)

