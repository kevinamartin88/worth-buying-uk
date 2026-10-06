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
try:
    import cairosvg
except (ImportError, OSError):
    cairosvg = None
from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.refresh_badge import updated_badge_text as _updated_badge_text


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

RETAILER_LOGOS = {
    "sharper image": ROOT / "assets" / "retailers" / "sharper-image.svg",
}
RETAILER_DISPLAY_NAMES = {
    "choice furniture supersto": "Choice Furniture Superstore",
}

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


def _fit_single_line_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start_size: int,
    minimum_size: int,
):
    """Keep long retailer names inside their card without changing short names."""
    for size in range(start_size, minimum_size - 1, -1):
        font = _load_font(size, bold=True)
        if _measure(draw, text, font)[0] <= max_width:
            return font
    return _load_font(minimum_size, bold=True)


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
    if _has_any(haystack, "storage", "organisation", "organization", "organizer", "declutter", "hanger"):
        return "HOME ORGANISATION GUIDE"
    if _has_any(haystack, "cleaning bundle", "cleaning set"):
        return "CLEANING BUYING GUIDE"
    if _has_any(haystack, "portable griddle", "outdoor cooking"):
        return "OUTDOOR COOKING GUIDE"
    if _has_any(haystack, "smart light switch"):
        return "SMART HOME GUIDE"
    if _has_any(haystack, "streaming device", "fire tv", "roku"):
        return "STREAMING DEVICE GUIDE"
    if _has_any(haystack, "loungewear", "comfortable wear"):
        return "LIFESTYLE BUYING GUIDE"
    if _has_any(haystack, "beauty", "self-care", "self care"):
        return "BEAUTY BUYING GUIDE"
    if _has_any(haystack, "hobby", "craft kit"):
        return "HOBBY BUYING GUIDE"
    if _has_any(haystack, "diy", "home improvement", "tool kit", "drill", "garden tool"):
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


def _featured_retailer(article: dict) -> str:
    def display_name(value: object) -> str:
        clean = " ".join(str(value or "").split())
        return RETAILER_DISPLAY_NAMES.get(clean.casefold(), clean)

    explicit = str(article.get("featured_retailer") or "").strip()
    if explicit:
        return display_name(explicit)

    generator = article.get("_generator") or {}
    explicit = str(generator.get("featured_retailer") or "").strip()
    if explicit:
        return display_name(explicit)

    merchants = [str(value).strip() for value in generator.get("merchants", []) if str(value).strip()]
    return display_name(merchants[0]) if len(merchants) == 1 else ""


def _retailer_logo_path(article: dict) -> Path | None:
    retailer = _featured_retailer(article)
    explicit = str(
        article.get("retailer_logo_asset")
        or (article.get("_generator") or {}).get("retailer_logo_asset")
        or ""
    ).strip()
    candidate = ROOT / explicit if explicit else RETAILER_LOGOS.get(retailer.casefold())
    if candidate is None:
        return None
    try:
        resolved = candidate.resolve()
        resolved.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _load_retailer_logo(
    article: dict,
    max_width: int = 520,
    max_height: int = 42,
) -> Image.Image | None:
    path = _retailer_logo_path(article)
    if path is None:
        return None
    try:
        if path.suffix.casefold() == ".svg":
            if cairosvg is None:
                return None
            image_bytes = cairosvg.svg2png(bytestring=path.read_bytes(), output_width=max_width)
            logo = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        else:
            logo = Image.open(path).convert("RGBA")
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return logo.copy()
    except Exception:
        # A retailer logo problem must never stop the article or hero image.
        return None


def _article_style_version(article: dict) -> str:
    retailer = _featured_retailer(article)
    if retailer.casefold() == "choice furniture superstore":
        # Regenerate the already-published image that used Rakuten's shortened name.
        version = STYLE_VERSION + "+choice-furniture-name-fit-v1"
    else:
        version = STYLE_VERSION + ("+retailer-logo-v2" if retailer else "")

    if _has_any(_topic_haystack(article), "air fryer", "air-fryer"):
        version += "+air-fryer-subject-v3"

    updated_badge = _updated_badge_text(article)
    if updated_badge:
        badge_revision = re.sub(
            r"[^a-z0-9._-]+",
            "-",
            updated_badge.casefold(),
        ).strip("-")
        version += f"+updated-badge-v1-{badge_revision}"

    revision = re.sub(
        r"[^a-z0-9._-]+",
        "-",
        str(article.get("hero_visual_revision") or "").strip().casefold(),
    ).strip("-")
    return version + (f"+{revision}" if revision else "")


def _style_marker(output: Path) -> Path:
    return output.with_name(output.name + ".style")


def _is_current_style(output: Path, article: dict) -> bool:
    marker = _style_marker(output)
    if not output.exists() or not marker.exists():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == _article_style_version(article)
    except OSError:
        return False


def _write_style_marker(output: Path, article: dict) -> None:
    _style_marker(output).write_text(_article_style_version(article) + "\n", encoding="utf-8")


def _visual_direction(article: dict) -> str:
    haystack = _topic_haystack(article)

    # General buying-advice articles need an abstract shopping decision scene,
    # not literal interpretations of the word "shop" as a fashion store.
    if _has_any(haystack, "savvy buyer", "buying advice", "consumer tips"):
        return (
            "Create a clean consumer price-comparison editorial scene on a modern desk: a generic "
            "laptop showing an unreadable comparison-table layout, a calculator, a paper receipt, "
            "two or three plain unbranded product boxes and small blank price-tag shapes. Keep the "
            "scene realistic, calm and useful. Do not show people, faces, human figures, mannequins, "
            "clothing racks, fashion stores or fashion imagery. Do not include readable text."
        )

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

    if _has_any(haystack, "jump starter", "car jump starter", "battery booster"):
        return (
            "The HERO PRODUCT MUST be a large portable lithium car jump starter in the foreground, "
            "clearly visible and unmistakable, with heavy-duty red and black battery clamps/cables "
            "beside it. The jump starter must occupy roughly one third of the frame. A modern car may "
            "appear only as secondary background context, ideally with the bonnet/hood open or parked "
            "beside the product. Do not create a car-only image. Do not make the vehicle the main focal "
            "point. Use a cold-weather roadside or garage setting with subtle winter cues, realistic "
            "materials and premium automotive editorial lighting."
        )

    if _has_any(haystack, "breakdown", "emergency kit", "roadside", "safety kit"):
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
    if _has_any(haystack, "air fryer", "air-fryer"):
        return (
            "Show ONE unmistakable modern basket-style countertop air fryer as the hero product. "
            "It must have a solid opaque front, a horizontal pull-out drawer seam, a substantial drawer handle, "
            "and the drawer pulled partly open so the removable basket is clearly visible. A second matching "
            "drawer is acceptable for a dual-basket model. The appliance should be compact and sit entirely on "
            "a kitchen countertop. Do NOT show any transparent or glass front panel. Do NOT show an oven door, "
            "wire racks, baking trays, rotisserie cavity, toaster-oven shape, microwave shape, built-in oven, "
            "freestanding cooker/range, stovetop, hob or range hood. Do NOT make the air fryer resemble a mini oven. "
            "Use a bright realistic modern kitchen, with the air fryer large and obvious on the left side and "
            "clean negative space toward the centre-right for headline text."
        )

    if _has_any(haystack, "kitchen gadgets", "kitchen appliance", "coffee maker", "stand mixer", "cookware"):
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

    if _has_any(haystack, "storage", "organisation", "organization", "organizer", "shelving", "declutter", "hanger"):
        return (
            "Stage a home-organisation editorial scene with attractive unbranded storage bins, "
            "wardrobe organisers or hangers in a neat modern home environment. Make it feel clean, "
            "satisfying and useful."
        )

    if _has_any(haystack, "cleaning bundle", "cleaning set", "multi-purpose cleaning", "multipurpose cleaning"):
        return (
            "Stage a bright weekend-cleaning editorial with a tasteful unbranded bundle of household "
            "cleaning tools, cloths, sprays and brushes arranged in a fresh utility-room or kitchen setting."
        )

    if _has_any(haystack, "portable griddle", "outdoor cooking"):
        return (
            "Stage a relaxed outdoor-cooking editorial with a compact unbranded portable griddle on a "
            "patio or garden table, with tasteful food-preparation props and no visible logos."
        )

    if _has_any(haystack, "loungewear", "comfortable wear"):
        return (
            "Stage a premium lifestyle editorial with neatly folded or casually arranged comfortable "
            "unbranded loungewear in a warm, modern bedroom or lounge setting. No models are required."
        )

    if _has_any(haystack, "beauty", "self-care", "self care"):
        return (
            "Stage a refined self-care editorial with a small collection of unbranded beauty and grooming "
            "products on a clean vanity or bathroom surface, using soft natural light and premium styling."
        )

    if _has_any(haystack, "hobby", "craft kit"):
        return (
            "Stage a colourful but tasteful hobby-and-craft editorial with unbranded creative materials "
            "arranged on a clean table, suggesting a relaxed weekend project without readable packaging."
        )

    if _has_any(haystack, "smart light switch"):
        return (
            "Stage a modern smart-home editorial showing a generic unbranded smart light switch in a "
            "stylish contemporary room, with subtle connected-home context and no visible logos."
        )

    if _has_any(haystack, "streaming device", "fire tv", "roku"):
        return (
            "Stage a premium home-entertainment editorial with a modern television and a small generic "
            "streaming device or remote in the foreground. Use abstract screen imagery only and no logos."
        )

    if _has_any(haystack, "diy", "home improvement", "tool kit", "drill", "decorating", "garden tool"):
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


def negative_prompt(article: dict | None = None) -> str:
    base = (
        "text, words, prices, sale badges, logos, trademarks, watermarks, brand names, QR codes, "
        "screenshots, distorted lettering, malformed products, impossible geometry, mannequins, extra limbs, "
        "extra fingers, duplicate objects, low resolution, blurry, oversaturated, cartoon, CGI, "
        "plastic-looking materials"
    )
    if article and _has_any(_topic_haystack(article), "air fryer", "air-fryer"):
        return (
            base
            + ", oven, conventional oven, wall oven, built-in oven, cooker, range, stove, stovetop, hob, "
            "toaster oven, mini oven, convection oven, air fryer oven, glass door, transparent door, "
            "oven cavity, oven rack, wire rack, baking tray, rotisserie"
        )
    return base


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

    # Refreshed daily features get a clear date badge on the site/social thumbnail.
    updated_badge = _updated_badge_text(article)
    retailer_card_bottom = badge_y2
    if updated_badge:
        updated_font = _load_font(24, bold=True)
        updated_w, updated_h = _measure(draw, updated_badge, updated_font)
        updated_y1 = badge_y2 + 14
        updated_y2 = updated_y1 + updated_h + 24
        draw.rounded_rectangle(
            (text_x, updated_y1, text_x + updated_w + 42, updated_y2),
            radius=16,
            fill=(253, 189, 32, 246),
        )
        draw.text(
            (text_x + 21, updated_y1 + 9),
            updated_badge,
            font=updated_font,
            fill=DEEP_NAVY,
        )
        retailer_card_bottom = updated_y2

    # A single-retailer Rakuten roundup gets an immediately visible retailer card.
    retailer = _featured_retailer(article)
    if retailer:
        card_y1 = retailer_card_bottom + 18
        card_y2 = card_y1 + 104
        draw.rounded_rectangle(
            (text_x, card_y1, text_x + text_max_width, card_y2),
            radius=18,
            fill=(255, 255, 255, 246),
            outline=(16, 183, 176, 255),
            width=3,
        )
        label_font = _load_font(16, bold=True)
        draw.text((text_x + 22, card_y1 + 10), "FEATURED RETAILER", font=label_font, fill=DEEP_NAVY)
        retailer_logo = _load_retailer_logo(article)
        if retailer_logo is not None:
            logo_x = text_x + (text_max_width - retailer_logo.width) // 2
            logo_y = card_y1 + 48
            image.alpha_composite(retailer_logo, (logo_x, logo_y))
            draw = ImageDraw.Draw(image)
        else:
            retailer_font = _fit_single_line_font(
                draw,
                retailer,
                max_width=text_max_width - 44,
                start_size=34,
                minimum_size=22,
            )
            retailer_w, retailer_h = _measure(draw, retailer, retailer_font)
            draw.text(
                (text_x + (text_max_width - retailer_w) // 2, card_y1 + 48 - retailer_h // 4),
                retailer,
                font=retailer_font,
                fill=DEEP_NAVY,
            )
        retailer_card_bottom = card_y2

    # Kicker pill.
    kicker_w, kicker_h = _measure(draw, kicker, kicker_font)
    kicker_y = retailer_card_bottom + 24
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
    _write_style_marker(output, article)


def _save_generated_image(
    image_bytes: bytes,
    output: Path,
    article: dict,
    market: str,
) -> None:
    with Image.open(io.BytesIO(image_bytes)) as image:
        _save_branded_image(image, output, article, market)


def _air_fryer_product_candidate(article: dict) -> tuple[str, str] | None:
    """Pick a real basket-style air fryer product photo already used in the article.

    AI image models can still turn the words "air fryer" into toaster-oven style
    appliances even with a strong negative prompt. For air-fryer guides we avoid
    that ambiguity by reusing an approved retailer product image whose listing
    title clearly describes a basket/drawer air fryer and does not describe an
    oven-style appliance.
    """
    content = str(article.get("content_html") or "")
    forbidden = (
        "oven",
        "rotisserie",
        "toaster",
        "convection",
        "french door",
        "glass door",
    )

    for tag in re.findall(r"<img\b[^>]*>", content, flags=re.IGNORECASE):
        src_match = re.search(r'\bsrc="([^"]+)"', tag, flags=re.IGNORECASE)
        alt_match = re.search(r'\balt="([^"]*)"', tag, flags=re.IGNORECASE)
        if not src_match or not alt_match:
            continue

        alt = html.unescape(alt_match.group(1)).strip()
        label = " ".join(alt.casefold().split())
        if "air fryer" not in label and "airfryer" not in label:
            continue
        if any(term in label for term in forbidden):
            continue

        image_url = html.unescape(src_match.group(1)).strip()
        if not image_url.startswith(("https://", "http://")):
            continue

        # eBay article thumbnails are often stored at s-l225; request the
        # higher-resolution variant for the hero whenever that URL pattern is used.
        image_url = re.sub(
            r"/s-l\d+\.(jpe?g|png)(?:\?.*)?$",
            lambda match: f"/s-l1600.{match.group(1)}",
            image_url,
            flags=re.IGNORECASE,
        )
        return image_url, alt

    return None


def _save_air_fryer_product_hero(
    image_bytes: bytes,
    output: Path,
    article: dict,
    market: str,
) -> None:
    """Build a deterministic hero from a real basket-style product image."""
    with Image.open(io.BytesIO(image_bytes)) as product:
        product = product.convert("RGB")
        canvas = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (244, 247, 250))
        panel = Image.new("RGB", (900, OUTPUT_HEIGHT), (255, 255, 255))
        fitted = ImageOps.contain(
            product,
            (820, 820),
            method=Image.Resampling.LANCZOS,
        )
        x = max(0, (panel.width - fitted.width) // 2)
        y = max(0, (panel.height - fitted.height) // 2)
        panel.paste(fitted, (x, y))
        canvas.paste(panel, (0, 0))
        _save_branded_image(canvas, output, article, market)


def _generate_air_fryer_product_hero(
    article: dict,
    market: str,
    output: Path,
) -> bool:
    candidate = _air_fryer_product_candidate(article)
    if candidate is None:
        return False

    image_url, title = candidate
    response = requests.get(
        image_url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "WorthBuyingVisualGenerator/4.3"},
    )
    response.raise_for_status()
    _save_air_fryer_product_hero(response.content, output, article, market)
    print(f"[air-fryer-product-hero] {title}")
    return True


def generate_image(
    article: dict,
    market: str,
    output: Path,
    account_id: str,
    api_token: str,
    force: bool = False,
) -> bool:
    if output.exists() and not force:
        if _is_current_style(output, article):
            return False
        # The saved JPG already contains its previous text overlay. Regenerate
        # the clean AI background before applying a changed layout, otherwise
        # old and new headlines would be layered on top of one another.

    # Air-fryer guides use a verified basket-style retailer product photo
    # rather than trusting a generative model to distinguish a drawer air fryer
    # from an oven-style appliance. If no suitable product photo is available,
    # fall back to the normal Cloudflare generation path below.
    if _has_any(_topic_haystack(article), "air fryer", "air-fryer"):
        try:
            if _generate_air_fryer_product_hero(article, market, output):
                return True
        except Exception as exc:
            print(
                f"[air-fryer-product-hero-warning] {article.get('slug', '')}: "
                f"{type(exc).__name__}: {exc}"
            )

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
        "negative_prompt": negative_prompt(article),
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
