from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT = 75
MODEL = "black-forest-labs/flux.1-schnell"


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def _seed_for(article: dict, market: str) -> int:
    raw = f"{market}:{article.get('slug','')}:{article.get('title','')}".encode("utf-8")
    # Pollinations currently accepts seeds up to 2,147,483,647.
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
    summary = _strip_html(str(article.get("content_html", "")))[:500]
    region = "United Kingdom" if market == "uk" else "United States"
    direction = _visual_direction(article)

    return (
        "Create a premium, photorealistic 16:9 editorial hero photograph for an independent "
        f"consumer buying guide in the {region}. "
        f"Article topic: {title}. "
        + (f"Relevant categories: {labels}. " if labels else "")
        + (f"Context: {summary}. " if summary else "")
        + direction
        + " Use natural believable lighting, realistic materials, clean magazine composition, "
        "strong depth and one clear visual focal point. Make it look like genuine commercial "
        "editorial photography rather than obvious AI art. Leave some uncluttered negative space "
        "near one side for responsive web cropping. No people unless genuinely useful to the scene. "
        "Do not include text, prices, sale badges, logos, trademarks, watermarks, brand names, "
        "screenshots, QR codes, distorted lettering, extra limbs, malformed products or impossible "
        "object geometry."
    )


def generate_image(article: dict, market: str, output: Path, api_key: str, force: bool = False) -> bool:
    if output.exists() and not force:
        return False

    prompt = build_prompt(article, market)
    seed = _seed_for(article, market)
    endpoint = "https://gen.pollinations.ai/image/" + quote(prompt, safe="")
    params = {
        "width": 1600,
        "height": 900,
        "seed": seed,
        "model": MODEL,
        "safe": "true",
    }

    response = requests.get(
        endpoint,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "WorthBuyingVisualGenerator/2.0",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "image" not in content_type:
        raise RuntimeError(f"Image service returned unexpected content type: {content_type}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)
    return True


def generate_market(market: str, force: bool = False) -> int:
    if market not in {"uk", "us"}:
        raise ValueError("market must be 'uk' or 'us'")

    api_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    if not api_key:
        print(
            "[ai-visual-skip] POLLINATIONS_API_KEY is not configured. "
            "Keeping the existing Pinterest artwork as the Blogger fallback."
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
                api_key=api_key,
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
