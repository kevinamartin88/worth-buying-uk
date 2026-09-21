from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT = 180


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def _seed_for(article: dict, market: str) -> int:
    raw = f"{market}:{article.get('slug','')}:{article.get('title','')}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def build_prompt(article: dict, market: str) -> str:
    title = str(article.get("title", "Worth Buying guide")).strip()
    labels = ", ".join(str(x) for x in article.get("labels", []) if str(x).strip())
    summary = _strip_html(str(article.get("content_html", "")))[:700]
    region = "United Kingdom" if market == "uk" else "United States"

    return (
        "Create a premium, photorealistic editorial lifestyle image for an independent "
        f"consumer buying guide in the {region}. "
        f"Article title: {title}. "
        + (f"Relevant topics: {labels}. " if labels else "")
        + (f"Article context: {summary}. " if summary else "")
        + "Show a believable, attractive scene with products or objects relevant to the guide. "
        "Use natural lighting, strong composition, realistic materials, visual depth, and a clean "
        "high-end magazine style. Leave useful negative space for web layout. "
        "Do not include text, prices, logos, trademarks, watermarks, badges, fake brand names, "
        "UI screenshots, or distorted lettering. Avoid hands unless essential."
    )


def generate_image(article: dict, market: str, output: Path, force: bool = False) -> bool:
    if output.exists() and not force:
        return False

    prompt = build_prompt(article, market)
    seed = _seed_for(article, market)
    endpoint = "https://image.pollinations.ai/prompt/" + quote(prompt, safe="")
    params = {
        "width": 1600,
        "height": 900,
        "seed": seed,
        "model": "flux",
        "nologo": "true",
        "safe": "true",
        "enhance": "true",
    }

    response = requests.get(
        endpoint,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "WorthBuyingVisualGenerator/1.0"},
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
            changed = generate_image(article, market, target, force=force)
        except Exception as exc:
            # Visuals should enhance publishing, not block an otherwise valid article.
            print(f"[ai-visual-warning] {slug}: {type(exc).__name__}: {exc}")
            continue

        if changed:
            count += 1
            print(f"[ai-visual] {target.relative_to(ROOT)}")
        else:
            print(f"[ai-visual-skip] {target.relative_to(ROOT)} already exists")

    return count
