from __future__ import annotations

import argparse
import io
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1600, 900

NAVY = (20, 35, 58)
TEAL = (29, 155, 149)
YELLOW = (248, 196, 66)
OFF_WHITE = (248, 249, 251)
MUTED = (190, 202, 215)
DARK_TEAL = (20, 112, 109)


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words = " ".join(str(text).split()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and words:
        joined = " ".join(lines)
        original = " ".join(words)
        if len(joined) < len(original):
            last = lines[-1]
            while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
                last = last[:-1].rstrip()
            lines[-1] = last + "…"
    return lines


def category_kicker(labels: list[str]) -> str:
    lowered = {str(label).casefold() for label in labels}
    if {"kitchen", "home", "appliances"} & lowered:
        return "HOME & KITCHEN GUIDE"
    if {"gaming", "playstation"} & lowered:
        return "GAMING BUYING GUIDE"
    if {"jewellery", "jewelry"} & lowered:
        return "SMARTER JEWELLERY BUYING"
    if {"garage tools", "motoring", "workshop equipment"} & lowered:
        return "GARAGE & TOOLS GUIDE"
    if {"apple", "samsung", "technology", "tech", "wearables"} & lowered:
        return "TECH BUYING GUIDE"
    return "SMARTER SHOPPING GUIDE"


def render(article: dict, market: str) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)

    # Decorative blocks keep the artwork branded without looking like a plain text card.
    draw.rounded_rectangle((1110, -70, 1660, 370), radius=90, fill=TEAL)
    draw.ellipse((1290, 120, 1670, 500), fill=DARK_TEAL)
    draw.rounded_rectangle((-90, 690, 620, 980), radius=120, fill=YELLOW)
    draw.ellipse((80, 705, 330, 955), fill=(238, 181, 39))

    brand = "WORTH BUYING UK" if market == "uk" else "WORTH BUYING USA"
    labels = list(article.get("labels", []))
    kicker = str(article.get("x_kicker") or category_kicker(labels)).upper()
    title = str(article.get("x_image_title") or article.get("title") or "Worth Buying")
    subtitle = str(
        article.get("x_subtitle")
        or article.get("pinterest_subtitle")
        or "Practical checks before you spend"
    )

    font_brand = load_font(34, bold=True)
    font_kicker = load_font(32, bold=True)
    font_title = load_font(76, bold=True)
    font_sub = load_font(34, bold=False)
    font_chip = load_font(25, bold=True)

    draw.text((100, 75), brand, font=font_brand, fill=OFF_WHITE)
    draw.rounded_rectangle((100, 145, 560, 205), radius=30, fill=TEAL)
    draw.text((130, 157), kicker, font=font_kicker, fill=OFF_WHITE)

    title_lines = wrap_to_width(draw, title, font_title, 1040, 4)
    y = 255
    for line in title_lines:
        draw.text((100, y), line, font=font_title, fill=OFF_WHITE)
        y += 94

    y += 10
    sub_lines = wrap_to_width(draw, subtitle, font_sub, 980, 2)
    for line in sub_lines:
        draw.text((100, y), line, font=font_sub, fill=MUTED)
        y += 50

    chips = [str(label) for label in labels if str(label).casefold() not in {"uk", "usa", "buying guides", "ebay deals"}][:3]
    chip_x = 760
    chip_y = 755
    for chip in chips:
        text_box = draw.textbbox((0, 0), chip.upper(), font=font_chip)
        chip_w = text_box[2] + 54
        if chip_x + chip_w > 1510:
            break
        draw.rounded_rectangle((chip_x, chip_y, chip_x + chip_w, chip_y + 58), radius=29, fill=OFF_WHITE)
        draw.text((chip_x + 27, chip_y + 13), chip.upper(), font=font_chip, fill=NAVY)
        chip_x += chip_w + 18

    draw.text((105, 800), "READ THE FULL GUIDE →", font=font_kicker, fill=NAVY)

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def generate_market(market: str) -> int:
    article_dir = ROOT / ("articles" if market == "uk" else "articles-us")
    output_dir = ROOT / "assets" / "x" / market
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in sorted(article_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if article.get("x_enabled", True) is False:
            continue
        slug = article["slug"]
        png = render(article, market)
        target = output_dir / f"{slug}.png"
        if target.exists() and target.read_bytes() == png:
            continue
        target.write_bytes(png)
        count += 1
        print(f"[x-image] {target.relative_to(ROOT)}")
    print(f"Generated/updated {count} X image(s) for {market.upper()}.")
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["uk", "us", "all"], default="all")
    args = parser.parse_args()

    markets = ["uk", "us"] if args.market == "all" else [args.market]
    for market in markets:
        generate_market(market)


if __name__ == "__main__":
    main()
