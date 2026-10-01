from __future__ import annotations

import html
import hashlib
import json
import math
import re
import shutil
import subprocess
import textwrap
import wave
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


WIDTH = 1080
HEIGHT = 1920
SLIDE_DURATIONS = (3.0, 3.5, 3.5)
SHORT_SECONDS = sum(SLIDE_DURATIONS)
MUSIC_SAMPLE_RATE = 44_100
MARKET_CONFIG = {
    "uk": {
        "brand": "Worth Buying UK",
        "site": "worthbuyinguk.co.uk",
        "accent": "#ef233c",
        "logo": "worth-buying-uk-logo.png",
    },
    "us": {
        "brand": "Worth Buying USA",
        "site": "worthbuyingusa.com",
        "accent": "#ef233c",
        "logo": "worth-buying-usa-logo.png",
    },
}


def publication_fingerprint(article: dict, blog_url: str) -> str:
    value = json.dumps(
        {
            "slug": article.get("slug"),
            "source_sha": article.get("source_sha"),
            "title": article.get("title"),
            "blog_url": blog_url,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _HeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.buffer: list[str] = []
        self.headings: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"h2", "h3"}:
            self.active = True
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.active and tag in {"h2", "h3"}:
            value = html.unescape(" ".join(self.buffer))
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                self.headings.append(value)
            self.active = False


def extract_short_points(content_html: str, limit: int = 3) -> list[str]:
    parser = _HeadingParser()
    parser.feed(content_html)
    ignored = (
        "frequently asked",
        "related worth buying",
        "how we choose",
        "affiliate disclosure",
        "current picks at a glance",
    )
    points: list[str] = []
    for heading in parser.headings:
        cleaned = re.sub(r"^\d+[.)]\s*", "", heading).strip()
        if any(term in cleaned.casefold() for term in ignored):
            continue
        if cleaned and cleaned not in points:
            points.append(cleaned)
        if len(points) == limit:
            break
    return points


def article_short_points(article: dict, limit: int = 3) -> list[str]:
    supplied = article.get("youtube_short_points") or []
    points = [str(point).strip() for point in supplied if str(point).strip()]
    if points:
        return points[:limit]
    return extract_short_points(str(article.get("content_html", "")), limit=limit)


def short_title(article: dict) -> str:
    title = re.sub(r"\s+", " ", str(article.get("title", "Worth Buying guide"))).strip()
    suffix = " #Shorts"
    return title[: 100 - len(suffix)].rstrip(" -|:") + suffix


def short_description(article: dict, blog_url: str, market: str) -> str:
    config = MARKET_CONFIG[market]
    summary = str(
        article.get("x_subtitle")
        or article.get("pinterest_subtitle")
        or "A quick buying guide to help you compare the options that matter."
    ).strip()
    return (
        f"Read the complete guide: {blog_url}\n\n{summary}\n\n"
        "Prices, availability and product details can change. Check the full guide and "
        "retailer listing before buying.\n\n"
        f"#{config['brand'].replace(' ', '')} #BuyingGuide #Shorts"
    )


def _font_path(bold: bool) -> str | None:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    return next((path for path in candidates if Path(path).exists()), None)


def _font(size: int, bold: bool = False):
    path = _font_path(bold)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def _wrapped_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start: int):
    for size in range(start, 43, -4):
        font = _font(size, bold=True)
        lines = _wrapped_lines(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = _font(42, bold=True)
    return font, _wrapped_lines(draw, text, font, max_width)[:max_lines]


def _base_slide(
    hero_path: Path,
    logo_path: Path,
    accent: str,
    *,
    image_first: bool = False,
) -> Image.Image:
    hero = _cover(Image.open(hero_path), (WIDTH, HEIGHT))
    if image_first:
        hero = ImageEnhance.Brightness(hero).enhance(0.92)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (4, 23, 56, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for y in range(HEIGHT):
            alpha = max(0, min(205, int((y - 760) / 980 * 205)))
            overlay_draw.line((0, y, WIDTH, y), fill=(4, 23, 56, alpha))
    else:
        hero = ImageEnhance.Brightness(hero).enhance(0.48).filter(
            ImageFilter.GaussianBlur(2)
        )
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (4, 23, 56, 130))
    canvas = Image.alpha_composite(hero.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (72, 70, WIDTH - 72, 214), radius=30, fill=(255, 255, 255, 240)
    )
    logo = Image.open(logo_path).convert("RGBA")
    logo.thumbnail((WIDTH - 270, 104), Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, ((WIDTH - logo.width) // 2, 90))
    return canvas


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font,
    top: int,
    *,
    fill: str = "white",
    spacing: int = 22,
) -> int:
    y = top
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += box[3] - box[1] + spacing
    return y


def create_slide(
    hero_path: Path,
    logo_path: Path,
    *,
    accent: str,
    kicker: str,
    headline: str,
    subtext: str,
    slide_number: int,
    slide_count: int,
    image_first: bool = False,
) -> Image.Image:
    canvas = _base_slide(hero_path, logo_path, accent, image_first=image_first)
    draw = ImageDraw.Draw(canvas)
    kicker_font = _font(36, bold=True)
    kicker_text = kicker.upper()[:38]
    kicker_box = draw.textbbox((0, 0), kicker_text, font=kicker_font)
    draw.rounded_rectangle(
        (74, 286 if image_first else 330, 110 + kicker_box[2], 348 if image_first else 392),
        radius=26,
        fill=accent,
    )
    draw.text(
        (92, 296 if image_first else 340),
        kicker_text,
        font=kicker_font,
        fill="white",
    )

    max_lines = 3 if image_first else 4
    headline_font, headline_lines = _fit_font(
        draw, headline, WIDTH - 170, max_lines, 84
    )
    headline_top = 1110 if image_first else 540
    y = _draw_centered_lines(draw, headline_lines, headline_font, headline_top, spacing=24)
    y += 40
    sub_font = _font(42)
    sub_lines = _wrapped_lines(draw, subtext, sub_font, WIDTH - 210)[:3]
    _draw_centered_lines(draw, sub_lines, sub_font, y, fill="#f3f6fb", spacing=16)
    return canvas.convert("RGB")


def _write_retro_mall_music(path: Path, duration: float) -> Path:
    """Create a quiet, original lounge loop without external music licensing."""
    sample_count = int(MUSIC_SAMPLE_RATE * duration)
    chord_progression = (
        (261.63, 329.63, 392.00, 493.88),  # Cmaj7
        (220.00, 261.63, 329.63, 392.00),  # Am7
        (293.66, 349.23, 440.00, 523.25),  # Dm7
        (196.00, 246.94, 293.66, 349.23),  # G7
    )
    beat_seconds = 0.625
    frames = bytearray()
    for index in range(sample_count):
        t = index / MUSIC_SAMPLE_RATE
        chord = chord_progression[int(t / (beat_seconds * 2)) % len(chord_progression)]
        pad = sum(math.sin(2 * math.pi * frequency * t) for frequency in chord) / 4
        bass = math.sin(2 * math.pi * (chord[0] / 2) * t)
        beat_phase = t % beat_seconds
        bell_envelope = math.exp(-7.0 * beat_phase)
        bell = math.sin(2 * math.pi * chord[2] * 2 * t) * bell_envelope
        fade = min(1.0, t / 0.45, max(0.0, (duration - t) / 0.65))
        sample = (0.10 * pad + 0.045 * bass + 0.025 * bell) * fade
        value = max(-32767, min(32767, int(sample * 32767)))
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(MUSIC_SAMPLE_RATE)
        audio.writeframes(frames)
    return path


def build_short_video(
    article: dict,
    *,
    market: str,
    hero_path: Path,
    logo_path: Path,
    output_path: Path,
    work_dir: Path,
) -> Path:
    if market not in MARKET_CONFIG:
        raise ValueError(f"Unsupported market: {market}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to render YouTube Shorts")
    config = MARKET_CONFIG[market]
    points = article_short_points(article)
    fallback = [
        "Compare the exact model and specification",
        "Check warranty, condition and returns",
        "Verify the live price before you buy",
    ]
    points = (points + fallback)[:2]
    hook = str(
        article.get("x_subtitle")
        or article.get("pinterest_subtitle")
        or "A quick buyer-first comparison"
    )
    slides = [
        (
            str(article.get("hero_image_kicker") or "BUYING GUIDE"),
            str(article.get("title", "Worth Buying guide")),
            hook,
        ),
        (
            "TWO QUICK CHECKS",
            points[0],
            points[1],
        ),
        (
            "FULL GUIDE",
            "See every pick and buying check",
            f"Visit {config['site']} — link in the description.",
        ),
    ]
    work_dir.mkdir(parents=True, exist_ok=True)
    slide_paths: list[Path] = []
    for index, (kicker, headline, subtext) in enumerate(slides, start=1):
        slide = create_slide(
            hero_path,
            logo_path,
            accent=config["accent"],
            kicker=kicker,
            headline=headline,
            subtext=subtext,
            slide_number=index,
            slide_count=len(slides),
            image_first=index == 1,
        )
        slide_path = work_dir / f"slide-{index:02d}.png"
        slide.save(slide_path, optimize=True)
        slide_paths.append(slide_path)

    manifest = work_dir / "slides.txt"
    manifest_lines: list[str] = []
    for slide_path, duration in zip(slide_paths, SLIDE_DURATIONS, strict=True):
        safe_path = slide_path.resolve().as_posix().replace("'", "'\\''")
        manifest_lines.extend([f"file '{safe_path}'", f"duration {duration}"])
    manifest_lines.append(f"file '{slide_paths[-1].resolve().as_posix()}'")
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    music_path = _write_retro_mall_music(work_dir / "retro-mall.wav", SHORT_SECONDS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-i",
        str(music_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        "fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st=9.6:d=0.4,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-t",
        str(SHORT_SECONDS),
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path
