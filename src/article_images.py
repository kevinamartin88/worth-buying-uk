from __future__ import annotations

import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_AI_BASE = (
    "https://raw.githubusercontent.com/kevinamartin88/"
    "worth-buying-uk/main/assets/ai"
)
IMG_RE = re.compile(r"<img\b", re.IGNORECASE)


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
    return f"{RAW_AI_BASE}/{market}/{slug}.jpg"


def require_hero_image(market: str, slug: str) -> str:
    path = hero_image_path(market, slug)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(
            f"Publish blocked: required {market.upper()} hero image is missing: "
            f"{path.relative_to(ROOT)}"
        )
    return hero_image_url(market, slug)


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
    content = str(content or "")
    if image_url in content:
        return content, image_url
    return markup + content, image_url


def backfill_hero_if_missing(
    content: str,
    market: str,
    slug: str,
    title: str,
) -> tuple[str, str, bool]:
    content = str(content or "")
    markup, image_url = hero_image_html(market, slug, title)
    if has_any_image(content):
        return content, image_url, False
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
