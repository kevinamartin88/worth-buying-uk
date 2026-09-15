from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles-us"
OUTPUT_DIR = ROOT / "assets" / "pinterest" / "us"

WIDTH = 1000
HEIGHT = 1500
NAVY = "#082F5B"
DEEP_NAVY = "#052544"
TEAL = "#10B7B0"
PALE_TEAL = "#E7F8F7"
PALE_BLUE = "#EEF6FB"
YELLOW = "#FDBD20"
WHITE = "#FFFFFF"
GREY = "#5D6B78"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.load_default()


def measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = " ".join(text.split()).split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if measure(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def title_layout(draw: ImageDraw.ImageDraw, title: str):
    for size in range(82, 49, -2):
        font = load_font(size, bold=True)
        lines = wrap_text(draw, title, font, 820)
        if len(lines) <= 6:
            line_height = measure(draw, "Ag", font)[1] + 22
            if len(lines) * line_height <= 560:
                return font, lines
    font = load_font(50, bold=True)
    return font, wrap_text(draw, title, font, 820)[:6]


def round_pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, text: str, text_fill: str) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=28, fill=fill)
    font = load_font(28, bold=True)
    tw, th = measure(draw, text, font)
    draw.text(((x1 + x2 - tw) / 2, (y1 + y2 - th) / 2 - 2), text, font=font, fill=text_fill)


def draw_bag_icon(draw: ImageDraw.ImageDraw) -> None:
    x, y = 790, 64
    draw.rounded_rectangle((x, y + 52, x + 120, y + 156), radius=18, fill=TEAL)
    draw.arc((x + 28, y, x + 92, y + 88), start=180, end=360, fill=WHITE, width=12)
    draw.line((x + 36, y + 103, x + 54, y + 121), fill=WHITE, width=11)
    draw.line((x + 54, y + 121, x + 88, y + 83), fill=WHITE, width=11)
    draw.line((925, 70, 955, 45), fill=YELLOW, width=10)
    draw.line((938, 108, 974, 108), fill=YELLOW, width=10)


def draw_check_card(draw: ImageDraw.ImageDraw, x: int, y: int, number: str, heading: str, sub: str) -> None:
    draw.rounded_rectangle((x, y, x + 250, y + 190), radius=34, fill=WHITE, outline="#DCEAF2", width=3)
    draw.ellipse((x + 24, y + 24, x + 82, y + 82), fill=PALE_TEAL)
    num_font = load_font(25, bold=True)
    n_w, n_h = measure(draw, number, num_font)
    draw.text((x + 53 - n_w / 2, y + 53 - n_h / 2 - 1), number, font=num_font, fill=TEAL)
    draw.text((x + 24, y + 101), heading, font=load_font(27, bold=True), fill=NAVY)
    draw.text((x + 24, y + 140), sub, font=load_font(22), fill=GREY)


def render_article(article: dict, output: Path) -> None:
    title = str(article.get("pinterest_title") or article["title"])
    labels = [str(x) for x in article.get("labels", []) if str(x).strip()]
    lower_title = title.lower()
    kicker = str(article.get("pinterest_kicker") or (
        "DEALS & BUYING ADVICE" if any(word in lower_title for word in ("deal", "sale", "off")) else "US BUYING GUIDE"
    ))
    subtitle = str(article.get("pinterest_subtitle") or "Practical shopping guidance for US buyers")

    image = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 230), fill=NAVY)
    draw.text((70, 58), "Worth Buying", font=load_font(58, bold=True), fill=WHITE)
    draw.text((70, 126), "USA", font=load_font(66, bold=True), fill=TEAL)
    draw_bag_icon(draw)

    badge_font = load_font(27, bold=True)
    badge_w = min(520, measure(draw, kicker, badge_font)[0] + 70)
    draw.rounded_rectangle((70, 282, 70 + badge_w, 344), radius=31, fill=PALE_TEAL)
    draw.text((105, 297), kicker, font=badge_font, fill=NAVY)

    title_font, title_lines = title_layout(draw, title)
    y = 405
    line_height = measure(draw, "Ag", title_font)[1] + 22
    for line in title_lines:
        draw.text((70, y), line, font=title_font, fill=DEEP_NAVY)
        y += line_height

    y += 18
    draw.rounded_rectangle((70, y, 245, y + 12), radius=6, fill=YELLOW)
    y += 48
    subtitle_font = load_font(31)
    for line in wrap_text(draw, subtitle, subtitle_font, 820)[:2]:
        draw.text((70, y), line, font=subtitle_font, fill=GREY)
        y += 47

    label_y = max(y + 42, 900)
    x = 70
    shown = 0
    for label in labels:
        clean = label.strip()
        if not clean or clean.lower() in {"usa", "us", "ebay", "amazon", "buying guides"}:
            continue
        label_font = load_font(24, bold=True)
        tw, _ = measure(draw, clean, label_font)
        width = min(tw + 60, 310)
        if x + width > 930:
            break
        round_pill(draw, (x, label_y, x + width, label_y + 58), PALE_BLUE, clean[:20], NAVY)
        x += width + 18
        shown += 1
        if shown == 3:
            break

    cards_y = 1045
    draw_check_card(draw, 70, cards_y, "1", "Compare", "Price & value")
    draw_check_card(draw, 375, cards_y, "2", "Check", "Fit & details")
    draw_check_card(draw, 680, cards_y, "3", "Choose", "What suits you")

    footer_top = 1295
    draw.rectangle((0, footer_top, WIDTH, HEIGHT), fill=DEEP_NAVY)
    draw.text((70, 1343), "Read the full guide at", font=load_font(28), fill="#B9D7E8")
    draw.text((70, 1385), "worthbuyingusa.blogspot.com", font=load_font(34, bold=True), fill=WHITE)
    draw.rounded_rectangle((70, 1442, 350, 1452), radius=5, fill=YELLOW)
    affiliate = "Some links may be affiliate links"
    a_font = load_font(20)
    a_w, _ = measure(draw, affiliate, a_font)
    draw.text((930 - a_w, 1431), affiliate, font=a_font, fill="#B9D7E8")

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def main() -> None:
    if not ARTICLES_DIR.exists():
        print("No USA articles directory found.")
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if article.get("pinterest_enabled", True) is False:
            continue
        slug = article["slug"]
        output = OUTPUT_DIR / f"{slug}.png"
        render_article(article, output)
        count += 1
        print(f"[pinterest-image-us] {output.relative_to(ROOT)}")
    print(f"Generated {count} USA Pinterest image(s).")


if __name__ == "__main__":
    main()
