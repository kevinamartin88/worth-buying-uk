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


def _fit_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    max_width: int = 620,
) -> tuple[object, list[str]]:
    for size in range(72, 49, -2):
        font = _load_font(size, bold=True)
        lines = _wrap_text(draw, title, font, max_width=max_width, max_lines=4)
        line_height = _measure(draw, "Ag", font)[1] + 16
        if len(lines) <= 4 and len(lines) * line_height <= 320:
            return font, lines

    font = _load_font(50, bold=True)
    return font, _wrap_text(draw, title, font, max_width=max_width, max_lines=4)


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


def _topic_haystack(article: dict) -> str:
    bits = [str(article.get("title", ""))]
    bits.extend(str(x) for x in article.get("labels", []))
    bits.append(str(article.get("hero_image_kicker", "")))
    bits.append(str(article.get("hero_image_subtitle", "")))
    return " ".join(bits).casefold()


def _has_any(haystack: str, *terms: str) -> bool:
    return any(term.casefold() in haystack for term in terms)


def _overlay_kicker(article: dict) -> str:
    explicit = str(
        article.get("hero_image_kicker")
        or article.get("x_kicker")
        or article.get("pinterest_kicker")
        or ""
    ).strip()
    if explicit:
        return explicit.upper()

    haystack = _topic_haystack(article)

    if _has_any(haystack, "garage tools", "workshop equipment", "socket set", "tyre inflator"):
        return "GARAGE TOOLS GUIDE"
    if _has_any(haystack, "car accessories", "phone mount", "seat organiser", "seat organizer", "dash cam"):
        return "CAR ACCESSORIES GUIDE"
    if _has_any(haystack, "car cleaning", "detailing", "car care"):
        return "CAR CARE GUIDE"
    if _has_any(haystack, "breakdown", "emergency kit", "jump starter", "roadside"):
        return "EMERGENCY GEAR GUIDE"

    if _has_any(haystack, "ipad", "tablet", "iphone", "smartphone", "refurbished phone", "refurbished ipad"):
        return "MOBILE TECH GUIDE"
    if _has_any(haystack, "laptop", "computer accessories", "monitor", "workspace"):
        return "WORKSPACE TECH GUIDE"
    if _has_any(haystack, "headphones", "earbuds", "speakers", "audio"):
        return "AUDIO TECH GUIDE"
    if _has_any(haystack, "smart home", "home tech", "security camera", "video doorbell"):
        return "SMART HOME GUIDE"

    if _has_any(haystack, "kitchen gadgets", "kitchen appliance", "air fryer", "coffee maker", "stand mixer", "cookware"):
        return "HOME & KITCHEN GUIDE"
    if _has_any(haystack, "cleaning appliance", "vacuum", "steam cleaner"):
        return "HOME CLEANING GUIDE"
    if _has_any(haystack, "storage", "organisation", "organization", "organizer", "declutter"):
        return "HOME ORGANISATION GUIDE"
    if _has_any(haystack, "diy", "home improvement", "tool kit", "drill"):
        return "DIY & HOME GUIDE"

    if _has_any(haystack, "diamond", "diamond jewelry", "diamond jewellery", "engagement ring"):
        return "JEWELLERY BUYING GUIDE"
    if _has_any(haystack, "watch", "watches", "timepiece"):
        return "WATCH BUYING GUIDE"
    if _has_any(haystack, "bag", "handbag", "wallet", "fashion accessory"):
        return "FASHION ACCESSORIES GUIDE"

    if _has_any(haystack, "console accessories", "controller", "charging dock", "gaming headset"):
        return "GAMING ACCESSORIES GUIDE"
    if _has_any(haystack, "gaming setup", "gaming desk", "streaming setup", "rgb"):
        return "GAMING SETUP GUIDE"
    if _has_any(haystack, "portable gaming", "handheld gaming"):
        return "PORTABLE GAMING GUIDE"

    if _has_any(haystack, "motoring", "automotive", "car", "garage", "workshop"):
        return "MOTORING BUYING GUIDE"
    if _has_any(haystack, "gaming", "playstation", "xbox", "nintendo"):
        return "GAMING BUYING GUIDE"
    if _has_any(haystack, "jewellery", "jewelry", "fashion"):
        return "JEWELLERY BUYING GUIDE"
    if _has_any(haystack, "tech", "technology", "electronics", "gadgets"):
        return "TECH BUYING GUIDE"
    if _has_any(haystack, "home", "kitchen", "appliance"):
        return "HOME & KITCHEN GUIDE"
    if _has_any(haystack, "deal", "sale", "discount", "off"):
        return "DEALS & BUYING ADVICE"

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
    haystack = _topic_haystack(article)

    # Motoring
    if _has_any(haystack, "garage tools", "workshop equipment", "socket set", "tool chest", "tyre inflator"):
        return (
            "Stage a clean modern garage workshop editorial scene with a sturdy workbench, "
            "tool chest, socket set, tyre inflator or inspection light, and a partial car softly "
            "in the background. The image should feel practical, premium and useful rather than messy."
        )

    if _has_any(haystack, "car accessories", "phone mount", "car organiser", "car organizer", "seat organiser", "seat organizer", "dash cam", "interior accessories"):
        return (
            "Stage a premium car-accessories editorial scene inside a modern vehicle interior, "
            "showing useful unbranded accessories such as a phone mount, organiser, charger or "
            "storage solution. Keep it realistic, tidy and visually appealing."
        )

    if _has_any(haystack, "car cleaning", "detailing", "car care", "wash kit", "microfiber", "microfibre", "polish"):
        return (
            "Stage a polished car-detailing editorial scene with a clean vehicle, detailing sprays, "
            "microfibre cloths, brushes or wash accessories arranged neatly. Use glossy reflections "
            "and premium automotive lifestyle styling."
        )

    if _has_any(haystack, "breakdown", "emergency kit", "jump starter", "roadside", "safety kit"):
        return (
            "Stage a roadside-emergency motoring editorial scene with useful unbranded items such as "
            "a jump starter, torch, safety vest, tyre inflator or compact emergency kit. Make it feel "
            "reassuring, practical and high quality."
        )

    if _has_any(haystack, "motoring", "automotive", "car", "garage", "workshop"):
        return (
            "Stage a clean modern motoring editorial scene with a partial car in the background and "
            "a curated set of useful unbranded motoring tools or accessories arranged naturally. "
            "Make it feel premium, practical and believable."
        )

    # Technology
    if _has_any(haystack, "ipad", "tablet", "iphone", "samsung phone", "smartphone", "refurbished phone", "refurbished ipad"):
        return (
            "Stage a premium consumer-tech editorial with two or three pristine generic mobile devices "
            "on a clean desk or studio surface. Screens should show only soft abstract colour gradients. "
            "Avoid recognisable logos, interfaces or exact trademarked product designs."
        )

    if _has_any(haystack, "laptop", "computer accessories", "monitor", "keyboard", "mouse", "workspace"):
        return (
            "Stage a clean modern workspace editorial scene with a generic laptop or monitor setup, "
            "plus tasteful accessories such as keyboard, mouse or desk essentials. Make it look sleek, "
            "productive and premium."
        )

    if _has_any(haystack, "headphones", "earbuds", "speakers", "audio", "sound"):
        return (
            "Stage a premium audio-tech editorial with unbranded headphones, earbuds or speakers in a "
            "clean listening setup. The scene should feel stylish, minimal and high-end."
        )

    if _has_any(haystack, "smart home", "home tech", "smart plug", "security camera", "video doorbell"):
        return (
            "Stage a smart-home editorial scene in a bright modern home environment, featuring generic "
            "smart-home devices such as plugs, lights, cameras or doorbell-style products. Keep it polished and realistic."
        )

    if _has_any(haystack, "tech", "technology", "electronics", "gadgets"):
        return (
            "Stage a premium consumer-tech editorial with a small curated set of generic modern devices "
            "in a clean, stylish environment. The image should feel contemporary, crisp and trustworthy."
        )

    # Gaming
    if _has_any(haystack, "console accessories", "controller", "charging dock", "gaming headset"):
        return (
            "Stage a gaming-accessories editorial with generic controller-shaped accessories, charging "
            "dock or headset items in a stylish desk setup with atmospheric lighting. Avoid all logos "
            "and copyrighted game imagery."
        )

    if _has_any(haystack, "gaming setup", "rgb", "gaming desk", "streaming setup"):
        return (
            "Stage a modern gaming-desk editorial with a stylish setup, ambient lighting, peripherals "
            "and a premium enthusiast feel. Keep the hardware generic and unbranded."
        )

    if _has_any(haystack, "portable gaming", "handheld gaming", "travel gaming"):
        return (
            "Stage a portable-gaming editorial showing generic handheld-gaming style accessories in a "
            "clean compact setup. Keep it modern, sleek and unbranded."
        )

    if _has_any(haystack, "gaming", "playstation", "xbox", "nintendo"):
        return (
            "Stage a modern gaming editorial with generic accessories, headphones and moody desk lighting. "
            "Avoid recognisable console logos, game art or copyrighted characters."
        )

    # Home and kitchen
    if _has_any(haystack, "kitchen gadgets", "kitchen appliance", "air fryer", "coffee maker", "stand mixer", "cookware"):
        return (
            "Stage a bright modern kitchen editorial with three or four relevant unbranded kitchen products "
            "such as an air fryer, coffee maker, mixer or cookware item arranged naturally. The scene should "
            "feel aspirational but real."
        )

    if _has_any(haystack, "cleaning appliance", "vacuum", "steam cleaner", "floor cleaner", "cleaning tools"):
        return (
            "Stage a clean home-care editorial scene featuring useful unbranded cleaning appliances or "
            "tools in a tidy utility room or home setting. The look should be fresh, practical and premium."
        )

    if _has_any(haystack, "storage", "organisation", "organization", "organizer", "shelving", "declutter"):
        return (
            "Stage a home-organisation editorial scene with attractive unbranded storage and organisation "
            "products in a neat modern home environment. Make it feel clean, satisfying and useful."
        )

    if _has_any(haystack, "diy", "home improvement", "tool kit", "drill", "decorating"):
        return (
            "Stage a home-improvement editorial scene with useful unbranded DIY tools or equipment in a "
            "smart workshop or home-renovation setting. Keep it tidy, capable and premium."
        )

    if _has_any(haystack, "home", "kitchen", "appliance", "cookware"):
        return (
            "Stage a bright modern kitchen or utility-room editorial with a curated group of useful "
            "unbranded household products. Make the scene feel realistic, tidy and premium."
        )

    # Jewellery and fashion
    if _has_any(haystack, "diamond", "diamond jewelry", "diamond jewellery", "engagement ring"):
        return (
            "Stage an elegant luxury jewellery editorial with unbranded diamond-style rings, earrings or "
            "a pendant on a refined neutral surface, with subtle velvet or stone textures and realistic sparkle."
        )

    if _has_any(haystack, "watch", "watches", "timepiece"):
        return (
            "Stage a refined luxury-watch editorial with one or two elegant unbranded watches on a tasteful "
            "surface, using premium lighting and crisp product detail."
        )

    if _has_any(haystack, "bag", "handbag", "fashion accessory", "wallet"):
        return (
            "Stage a stylish fashion-accessories editorial with elegant unbranded bags or small accessories "
            "in a premium lifestyle setting. Keep it polished and modern."
        )

    if _has_any(haystack, "jewellery", "jewelry", "fashion", "accessories"):
        return (
            "Stage an elegant fashion or jewellery editorial with refined styling, premium lighting and a "
            "small curated set of unbranded accessories."
        )

    return (
        "Stage a believable editorial scene with a small, curated selection of products directly relevant "
        "to the article. Prefer one coherent environment over a collage or product grid."
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
        "editorial photography. Place the main product or visual focal point on the left or "
        "left-centre of the frame. Keep the centre-right area relatively uncluttered because "
        "accurate headline text will be added there afterwards by the publishing system. "
        "Avoid placing important product details at the extreme left or right edges because "
        "social and website thumbnails may crop the image."
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

    # Keep all important wording inside a centre-right thumbnail-safe zone.
    # Many blog/social previews crop a 16:9 image toward the centre, so avoiding
    # the extreme left and right edges keeps the headline readable at small sizes.
    overlay_draw = ImageDraw.Draw(overlay)
    panel_left = 560
    panel_right = 1450
    for x in range(panel_left, panel_right):
        progress = (x - panel_left) / max(panel_right - panel_left - 1, 1)
        alpha = int(105 + (65 * progress))
        overlay_draw.rectangle((x, 0, x + 1, OUTPUT_HEIGHT), fill=(3, 23, 43, alpha))

    # Soft fade into the text panel from the image side.
    fade_left = 420
    for x in range(fade_left, panel_left):
        progress = (x - fade_left) / max(panel_left - fade_left - 1, 1)
        alpha = int(105 * progress)
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
    text_x = 620
    text_max_width = 620
    title_font, title_lines = _fit_title(draw, title, max_width=text_max_width)
    subtitle_font = _load_font(30)

    # Brand badge.
    brand_w, brand_h = _measure(draw, brand, brand_font)
    badge_x1, badge_y1 = text_x, 65
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
        (text_x, kicker_y, text_x + kicker_w + 46, kicker_y + kicker_h + 25),
        radius=18,
        fill=(16, 183, 176, 238),
    )
    draw.text((text_x + 23, kicker_y + 10), kicker, font=kicker_font, fill=WHITE)

    # Main headline.
    title_y = kicker_y + kicker_h + 72
    line_height = _measure(draw, "Ag", title_font)[1] + 18
    for line in title_lines:
        draw.text(
            (text_x, title_y),
            line,
            font=title_font,
            fill=WHITE,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 120),
        )
        title_y += line_height

    # Brand accent.
    accent_y = title_y + 12
    draw.rounded_rectangle((text_x, accent_y, text_x + 228, accent_y + 10), radius=5, fill=YELLOW)

    # Optional supporting line from the article metadata.
    if subtitle:
        sub_y = accent_y + 35
        for line in _wrap_text(draw, subtitle, subtitle_font, max_width=text_max_width, max_lines=2):
            draw.text((text_x, sub_y), line, font=subtitle_font, fill=MUTED_WHITE)
            sub_y += 44

    # Small footer prompt.
    footer_font = _load_font(25, bold=True)
    draw.text((text_x, 822), "READ THE FULL GUIDE", font=footer_font, fill=WHITE)
    draw.rounded_rectangle((text_x, 858, text_x + 173, 865), radius=4, fill=YELLOW)

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
            "User-Agent": "WorthBuyingVisualGenerator/4.2",
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
