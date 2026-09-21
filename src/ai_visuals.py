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
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT = 120
MODEL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"
WIDTH = 1600
HEIGHT = 900


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def _seed_for(article: dict, market: str) -> int:
    raw = f"{market}:{article.get('slug','')}:{article.get('title','')}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16) % 2_147_483_647


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
        "editorial photography. Leave some uncluttered negative space near one side for responsive "
        "web cropping."
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


def _save_as_jpeg(image_bytes: bytes, output: Path) -> None:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="JPEG", quality=90, optimize=True)


def generate_image(
    article: dict,
    market: str,
    output: Path,
    account_id: str,
    api_token: str,
    force: bool = False,
) -> bool:
    if output.exists() and not force:
        return False

    endpoint = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/ai/run/{MODEL}"
    )
    payload = {
        "prompt": build_prompt(article, market),
        "negative_prompt": negative_prompt(),
        "width": WIDTH,
        "height": HEIGHT,
        "num_steps": 20,
        "guidance": 7.5,
        "seed": _seed_for(article, market),
    }

    response = requests.post(
        endpoint,
        json=payload,
        timeout=REQUEST_TIMEOUT,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "WorthBuyingVisualGenerator/3.0",
        },
    )
    response.raise_for_status()

    image_bytes = _extract_image_bytes(response)
    _save_as_jpeg(image_bytes, output)
    return True


def generate_market(market: str, force: bool = False) -> int:
    if market not in {"uk", "us"}:
        raise ValueError("market must be 'uk' or 'us'")

    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        print(
            "[ai-visual-skip] CLOUDFLARE_ACCOUNT_ID and/or CLOUDFLARE_API_TOKEN "
            "is not configured. Keeping the existing Pinterest artwork as the Blogger fallback."
        )
        return 0

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
            print(f"[ai-visual-skip] {target.relative_to(ROOT)} already exists")

    return count
