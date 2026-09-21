from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT = 120
MODEL = "@cf/bytedance/stable-diffusion-xl-lightning"
GEN_WIDTH = 1024
GEN_HEIGHT = 576
OUTPUT_WIDTH = 1600
OUTPUT_HEIGHT = 900
STYLE_VERSION = "worth-buying-hero-text-v1"

NAVY = (8, 47, 91)
DEEP_NAVY = (5, 37, 68)
TEAL = (16, 183, 176)
YELLOW = (253, 189, 32)
WHITE = (255, 255, 255)
MUTED_WHITE = (225, 235, 241)

FONT_REGULAR_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)
FONT_BOLD_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
)


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def _seed_for(article: dict, market: str) -> int:
    raw = f"{market}:{article.get('slug','')}:{article.get('title','')}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16) % 2_147_483_647


def _load_font(size: int, bold: bool = False):
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = " ".join(str(text).split()).split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if _measure(draw, candidate, font)[0] <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
        current = word

        if len(lines) >= max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and words:
        visible = " ".join(lines)
        original = " ".join(words)
        if len(visible) < len(original):
            last = lines[-1]
            while last and _measure(draw, last + "…", font)[0] > max_width:
                last = last[:-1].rstrip()
            lines[-1] = (last or lines[-1]) + "…"

    return lines


def _fit_title(draw: ImageDraw.ImageDraw, title: str) -> tuple[object, list[str]]:
    for size in range(78, 53, -2):
        font = _load_font(size, bold=True)
        lines = _wrap_text(draw, title, font, max_width=860, max_lines=4)
        line_height = _measure(draw, "Ag", font)[1] + 18
        if len(lines) <= 4 and len(lines) * line_height <= 330:
            return font, lines

    font = _load_font(54, bold=True)
    return font, _wrap_text(draw, title, font, max_width=860, max_lines=4)


def _brand_name(market: str) -> str:
    return "WORTH BUYING UK" if market == "uk" else "WORTH BUYING USA"


def _overlay_title(article: dict) -> str:
    return str(
        article.get("hero_image_title")
        or article.get("x_image_title")
        or article.get("pinterest_title")
        or article.get("title")
        or "Worth Buying"
    ).strip()


def _overlay_kicker(article: dict) -> str:
    explicit = str(
        article.get("hero_image_kicker")
        or article.get("x_kicker")
        or article.get("pinterest_kicker")
        or ""
    ).strip()
    if explicit:
        return explicit.upper()

    title = str(article.get("title", "")).casefold()
    labels = {str(label).casefold() for label in article.get("labels", [])}

    if any(word in title for word in ("deal", "sale", "off")) or "deals" in labels:
        return "DEALS & BUYING ADVICE"
    if {"kitchen", "home", "appliances"} & labels:
        return "HOME & KITCHEN GUIDE"
    if {"motoring", "cars", "garage tools", "workshop equipment"} & labels:
        return "MOTORING BUYING GUIDE"
    if {"gaming", "playstation", "xbox", "nintendo"} & labels:
        return "GAMING BUYING GUIDE"
    if {"jewellery", "jewelry", "diamond jewelry"} & labels:
        return "JEWELLERY BUYING GUIDE"
    if {"tech", "technology", "apple", "samsung", "smartphones", "tablets"} & labels:
        return "TECH BUYING GUIDE"
    return "SMARTER SHOPPING GUIDE"


def _overlay_subtitle(article: dict) -> str:
    return str(
        article.get("hero_image_subtitle")
        or article.get("x_subtitle")
        or article.get("pinterest_subtitle")
        or ""
    ).strip()


def _style_marker(output: Path) -> Path:
    return output.with_name(output.name + ".style")


def _is_current_style(output: Path) -> bool:
    marker = _style_marker(output)
    if not output.exists() or not marker.exists():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == STYLE_VERSION
    except OSError:
        return False


def _write_style_marker(output: Path) -> None:
    _style_marker(output).write_text(STYLE_VERSION + "\n", encoding="utf-8")


def _visual_direction(article: dict) -> str:
    haystack = " ".join(
        [str(article.get("title", ""))]
        + [str(x) for x in article.get("labels", [])]
    ).casefold()

    if any(word in haystack for word in ("jewellery", "jewelry", "diamond")):
        return (
            "Stage an elegant luxury jewellery editorial: a small selection of unbranded "
            "diamond-style rings, earrings or a pendant on a refined neutral surface, subtle "
            "velvet or stone textures, crisp macro detail and realistic sparkle. Keep it tasteful "
            "and premium rather than flashy."
        )

    if any(word in haystack for word in ("kitchen", "home", "appliance", "cookware")):
        return (
            "Stage a bright modern kitchen or utility-room editorial with three or four relevant "
            "unbranded household products arranged naturally, such as an air fryer, coffee maker, "
            "stand mixer or compact cleaning appliance. The scene should feel lived-in but tidy, "
            "not like a catalogue grid."
        )

    if any(word in haystack for word in ("motoring", "garage", "car accessories", "workshop", "tools")):
        return (
            "Stage a clean modern garage/workshop scene with a partial car softly in the background "
            "and a curated set of useful unbranded accessories or tools on a workbench, such as a "
            "socket set, tyre inflator, inspection light or detailing equipment."
        )

    if any(word in haystack for word in ("iphone", "ipad", "samsung", "smartphone", "phone", "tablet", "refurbished", "tech")):
        return (
            "Stage a premium consumer-tech editorial with two or three pristine generic devices on "
            "a clean desk or studio surface. Screens should show only abstract colour gradients with "
            "no readable interface text. Do not copy any recognisable manufacturer logo or exact "
            "trademarked product design."
        )

    if any(word in haystack for word in ("gaming", "playstation", "xbox", "nintendo")):
        return (
            "Stage a modern gaming setup with generic unbranded controller-shaped accessories, "
            "headphones and atmospheric desk lighting. Avoid recognisable console logos, game art "
            "or copyrighted characters."
        )

    return (
        "Stage a believable editorial scene with a small, curated selection of products directly "
        "relevant to the article. Prefer one coherent environment over a collage or product grid."
    )


def build_prompt(article: dict, market: str) -> str:
    title = str(article.get("title", "Worth Buying guide")).strip()
    labels = ", ".join(str(x) for x in article.get("labels", []) if str(x).strip())
    summary = _strip_html(str(article.get("content_html", "")))[:450]
    region = "United Kingdom" if market == "uk" else "United States"
    direction = _visual_direction(article)

    return (
        "Premium photorealistic 16:9 editorial hero photograph for an independent "
        f"consumer buying guide in the {region}. "
        f"Article topic: {title}. "
        + (f"Relevant categories: {labels}. " if labels else "")
        + (f"Context: {summary}. " if summary else "")
        + direction
        + " Use believable natural lighting, realistic materials, clean magazine composition, "
        "strong depth and one clear visual focal point. Make it look like genuine commercial "
        "editorial photography. Keep the left side relatively uncluttered because accurate text "
        "will be added there afterwards by the publishing system."
    )


def negative_prompt() -> str:
    return (
        "text, words, prices, sale badges, logos, trademarks, watermarks, brand names, QR codes, "
        "screenshots, distorted lettering, malformed products, impossible geometry, extra limbs, "
        "extra fingers, duplicate objects, low resolution, blurry, oversaturated, cartoon, CGI, "
        "plastic-looking materials"
    )


def _extract_image_bytes(response: requests.Response) -> bytes:
    content_type = response.headers.get("content-type", "").lower()

    if "image/" in content_type or "application/octet-stream" in content_type:
        return response.content

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Cloudflare returned unexpected content type: {content_type or 'unknown'}"
        ) from exc

    result = payload.get("result")
    encoded = None

    if isinstance(result, dict):
        encoded = result.get("image") or result.get("image_b64")
    elif isinstance(result, str):
        encoded = result

    if not encoded:
        errors = payload.get("errors") or []
        raise RuntimeError(f"Cloudflare did not return image data. Errors: {errors}")

    try:
        return base64.b64decode(encoded)
    except Exception as exc:
        raise RuntimeError("Cloudflare returned image data that could not be decoded") from exc


def _add_text_overlay(image: Image.Image, article: dict, market: str) -> Image.Image:
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))

    # Strong left-hand gradient protects headline readability while preserving
    # the product photography on the right side of the image.
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_width = 1120
    for x in range(gradient_width):
        progress = x / max(gradient_width - 1, 1)
        alpha = int(218 * (1 - progress) ** 1.65)
        overlay_draw.rectangle((x, 0, x + 1, OUTPUT_HEIGHT), fill=(3, 23, 43, alpha))

    # A light bottom vignette keeps the lower call-to-action readable.
    for y in range(620, OUTPUT_HEIGHT):
        progress = (y - 620) / max(OUTPUT_HEIGHT - 620, 1)
        alpha = int(85 * progress)
        overlay_draw.rectangle((0, y, OUTPUT_WIDTH, y + 1), fill=(0, 0, 0, alpha))

    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    brand = _brand_name(market)
    kicker = _overlay_kicker(article)
    title = _overlay_title(article)
    subtitle = _overlay_subtitle(article)

    brand_font = _load_font(30, bold=True)
    kicker_font = _load_font(27, bold=True)
    title_font, title_lines = _fit_title(draw, title)
    subtitle_font = _load_font(30)

    # Brand badge.
    brand_w, brand_h = _measure(draw, brand, brand_font)
    badge_x1, badge_y1 = 82, 65
    badge_x2 = badge_x1 + brand_w + 54
    badge_y2 = badge_y1 + brand_h + 30
    draw.rounded_rectangle(
        (badge_x1, badge_y1, badge_x2, badge_y2),
        radius=20,
        fill=(8, 47, 91, 238),
        outline=(16, 183, 176, 255),
        width=3,
    )
    draw.text((badge_x1 + 27, badge_y1 + 13), brand, font=brand_font, fill=WHITE)

    # Kicker pill.
    kicker_w, kicker_h = _measure(draw, kicker, kicker_font)
    kicker_y = badge_y2 + 24
    draw.rounded_rectangle(
        (82, kicker_y, 82 + kicker_w + 46, kicker_y + kicker_h + 25),
        radius=18,
        fill=(16, 183, 176, 238),
    )
    draw.text((105, kicker_y + 10), kicker, font=kicker_font, fill=WHITE)

    # Main headline.
    title_y = kicker_y + kicker_h + 72
    line_height = _measure(draw, "Ag", title_font)[1] + 18
    for line in title_lines:
        draw.text(
            (82, title_y),
            line,
            font=title_font,
            fill=WHITE,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 120),
        )
        title_y += line_height

    # Brand accent.
    accent_y = title_y + 12
    draw.rounded_rectangle((82, accent_y, 310, accent_y + 10), radius=5, fill=YELLOW)

    # Optional supporting line from the article metadata.
    if subtitle:
        sub_y = accent_y + 35
        for line in _wrap_text(draw, subtitle, subtitle_font, max_width=820, max_lines=2):
            draw.text((82, sub_y), line, font=subtitle_font, fill=MUTED_WHITE)
            sub_y += 44

    # Small footer prompt.
    footer_font = _load_font(25, bold=True)
    draw.text((82, 822), "READ THE FULL GUIDE", font=footer_font, fill=WHITE)
    draw.rounded_rectangle((82, 858, 255, 865), radius=4, fill=YELLOW)

    return image.convert("RGB")


def _save_branded_image(image: Image.Image, output: Path, article: dict, market: str) -> None:
    image = image.convert("RGB")
    if image.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
        image = image.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.Resampling.LANCZOS)
    image = _add_text_overlay(image, article, market)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="JPEG", quality=91, optimize=True)
    _write_style_marker(output)


def _save_generated_image(
    image_bytes: bytes,
    output: Path,
    article: dict,
    market: str,
) -> None:
    with Image.open(io.BytesIO(image_bytes)) as image:
        _save_branded_image(image, output, article, market)


def _brand_existing_image(output: Path, article: dict, market: str) -> None:
    with Image.open(output) as image:
        # Existing Cloudflare backgrounds can be upgraded locally without using
        # another AI generation request.
        _save_branded_image(image.copy(), output, article, market)


def generate_image(
    article: dict,
    market: str,
    output: Path,
    account_id: str,
    api_token: str,
    force: bool = False,
) -> bool:
    if output.exists() and not force:
        if _is_current_style(output):
            return False
        _brand_existing_image(output, article, market)
        return True

    if not account_id or not api_token:
        raise RuntimeError(
            "Cloudflare credentials are required to generate a new AI background."
        )

    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/ai/run/{MODEL}"
    )
    payload = {
        "prompt": build_prompt(article, market),
        "negative_prompt": negative_prompt(),
        "width": GEN_WIDTH,
        "height": GEN_HEIGHT,
        "seed": _seed_for(article, market),
    }

    response = requests.post(
        endpoint,
        json=payload,
        timeout=REQUEST_TIMEOUT,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "WorthBuyingVisualGenerator/4.0",
        },
    )
    response.raise_for_status()

    image_bytes = _extract_image_bytes(response)
    _save_generated_image(image_bytes, output, article, market)
    return True


def generate_market(market: str, force: bool = False) -> int:
    if market not in {"uk", "us"}:
        raise ValueError("market must be 'uk' or 'us'")

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

    article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
    output_dir = ROOT / "assets" / "ai" / market
    if not article_dir.exists():
        return 0

    count = 0
    for path in sorted(article_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if article.get("ai_visual_enabled", True) is False:
            continue
        if str(article.get("mode", "publish")).strip().lower() != "publish":
            continue

        slug = str(article["slug"]).strip()
        target = output_dir / f"{slug}.jpg"

        if not target.exists() and (not account_id or not api_token):
            print(
                f"[ai-visual-skip] {slug}: Cloudflare credentials are not configured "
                "and no existing AI background is available."
            )
            continue

        try:
            changed = generate_image(
                article,
                market,
                target,
                account_id=account_id,
                api_token=api_token,
                force=force,
            )
        except Exception as exc:
            # Visuals enhance publishing but must never block a valid article.
            print(f"[ai-visual-warning] {slug}: {type(exc).__name__}: {exc}")
            continue

        if changed:
            count += 1
            print(f"[ai-visual] {target.relative_to(ROOT)}")
        else:
            print(f"[ai-visual-skip] {target.relative_to(ROOT)} already has current branding")

    return count
