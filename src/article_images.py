from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from PIL import Image
from src.product_image_quality import prepare_product_images


ROOT = Path(__file__).resolve().parents[1]
RAW_AI_BASE = (
    "https://raw.githubusercontent.com/kevinamartin88/"
    "worth-buying-uk/main/assets/ai"
)
IMG_RE = re.compile(r"<img\b", re.IGNORECASE)
HERO_RE = re.compile(
    r'<div\\s+class="wb-article-hero"[^>]*>.*?</div>\\s*',
    re.IGNORECASE | re.DOTALL,
)


def _validate_market(market: str) -> str:
    market = str(market).strip().lower()
    if market not in {"uk", "us"}:
        raise ValueError("market must be 'uk' or 'us'")
    return market


def hero_image_path(market: str, slug: str) -> Path:
    market = _validate_market(market)
    return ROOT / "assets" / "ai" / market / f"{slug}.jpg"


def hero_image_url(market: str, slug: str) -> str:
    market = _validate_market(market)
    url = f"{RAW_AI_BASE}/{market}/{slug}.jpg"

    # Refreshed/event artwork deliberately changes while keeping the same
    # article slug. Give those images a content-addressed URL so Blogger,
    # browsers and CDNs cannot keep serving the previous thumbnail.
    path = hero_image_path(market, slug)
    style_path = path.with_suffix(path.suffix + ".style")
    try:
        style = style_path.read_text(encoding="utf-8").strip().casefold()
    except OSError:
        style = ""
    if path.is_file() and ("updated-badge" in style or "prime-big" in style):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return f"{url}?v={digest}"
    return url


def validate_hero_file(path: Path) -> None:
    """Reject broken or undersized banners before any Blogger write."""
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            width, height = image.size
        if width < 900 or height < 450:
            raise ValueError(f"{width}x{height}; need at least 900x450")
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Publish blocked: invalid hero image {path.name}: {exc}") from exc


def require_hero_image(market: str, slug: str) -> str:
    """Return a required public article image, preferring the generated AI hero.

    This mirrors the proven email/manual route: use the wide AI hero when it
    exists, otherwise fall back to the Pinterest artwork. Publishing is blocked
    when neither image exists or the selected image is corrupt or undersized.
    """
    market = _validate_market(market)
    ai_path = hero_image_path(market, slug)
    if ai_path.is_file() and ai_path.stat().st_size > 0:
        validate_hero_file(ai_path)
        return hero_image_url(market, slug)

    if market == "uk":
        fallback_path = ROOT / "assets" / "pinterest" / f"{slug}.png"
        fallback_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/{slug}.png"
        )
    else:
        fallback_path = ROOT / "assets" / "pinterest" / "us" / f"{slug}.png"
        fallback_url = (
            "https://raw.githubusercontent.com/kevinamartin88/"
            f"worth-buying-uk/main/assets/pinterest/us/{slug}.png"
        )

    if fallback_path.is_file() and fallback_path.stat().st_size > 0:
        validate_hero_file(fallback_path)
        return fallback_url

    raise RuntimeError(
        f"Publish blocked: no required {market.upper()} article image exists for {slug} "
        "(AI hero and Pinterest fallback are both missing)."
    )


def hero_image_html(market: str, slug: str, title: str) -> tuple[str, str]:
    image_url = require_hero_image(market, slug)
    alt = html.escape(str(title), quote=True)
    markup = (
        '<div class="wb-article-hero" style="margin:0 0 26px 0;text-align:center;">'
        f'<img src="{image_url}" alt="{alt}" loading="eager" width="1600" height="900" '
        'style="width:100%;max-width:900px;height:auto;display:block;'
        'margin:0 auto;border-radius:16px;box-shadow:0 10px 30px rgba(8,47,91,.14);" />'
        '</div>\n'
    )
    return markup, image_url


def has_any_image(content: str) -> bool:
    return bool(IMG_RE.search(str(content or "")))


def add_required_hero(content: str, market: str, slug: str, title: str) -> tuple[str, str]:
    markup, image_url = hero_image_html(market, slug, title)
    content = prepare_product_images(str(content or ""))
    if image_url in content:
        return content, image_url
    if HERO_RE.search(content):
        return HERO_RE.sub(markup, content, count=1), image_url
    return markup + content, image_url


def backfill_hero_if_missing(
    content: str,
    market: str,
    slug: str,
    title: str,
) -> tuple[str, str, bool]:
    content = str(content or "")
    markup, image_url = hero_image_html(market, slug, title)
    if image_url in content:
        return content, image_url, False
    if HERO_RE.search(content):
        return HERO_RE.sub(markup, content, count=1), image_url, True
    return markup + content, image_url, True


def verify_required_hero(content: str, image_url: str, title: str) -> None:
    content = str(content or "")
    if not has_any_image(content) or image_url not in content:
        raise RuntimeError(
            f"Publish verification failed: Blogger stored '{title}' without the required hero image."
        )


def verify_any_image(content: str, title: str) -> None:
    if not has_any_image(str(content or "")):
        raise RuntimeError(
            f"Publish verification failed: Blogger stored '{title}' without any article image."
        )


