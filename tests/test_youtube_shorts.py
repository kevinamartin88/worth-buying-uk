import wave

from src.youtube_shorts import (
    HEIGHT,
    SHORT_SECONDS,
    SLIDE_DURATIONS,
    TEXT_MAX_WIDTH,
    WIDTH,
    _fit_font,
    _font,
    _wrapped_lines,
    create_slide,
    _write_retro_mall_music,
    article_short_points,
    extract_short_points,
    publication_fingerprint,
    short_description,
    short_title,
)


def test_short_timing_is_ten_seconds_across_three_clean_scenes():
    assert len(SLIDE_DURATIONS) == 3
    assert SHORT_SECONDS == 10


def test_retro_mall_music_is_a_valid_ten_second_wav(tmp_path):
    path = _write_retro_mall_music(tmp_path / "retro-mall.wav", SHORT_SECONDS)
    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 44_100
        assert audio.getnframes() == 441_000


def test_extract_short_points_ignores_boilerplate_sections():
    content = """
    <h2>1. First product worth comparing</h2>
    <h2>How to choose the right option</h2>
    <h2>Frequently asked questions</h2>
    <h3>2. Second useful product</h3>
    """
    assert extract_short_points(content) == [
        "First product worth comparing",
        "How to choose the right option",
        "Second useful product",
    ]


def test_short_metadata_is_regional_and_within_youtube_limits():
    article = {
        "title": "A" * 120,
        "pinterest_subtitle": "Three useful buying checks.",
    }
    assert len(short_title(article)) <= 100
    description = short_description(article, "https://www.worthbuyinguk.co.uk/post", "uk")
    assert description.startswith(
        "Read the complete guide: https://www.worthbuyinguk.co.uk/post"
    )
    assert "worthbuyinguk.co.uk/post" in description
    assert "affiliate" not in description.casefold()
    assert "#Shorts" in description


def test_generated_price_points_take_priority_over_headings():
    article = {
        "title": "Air fryers",
        "content_html": "<h3>Fallback heading</h3>",
        "youtube_short_points": ["New with tags — eBay £89.99 — Amazon £99.99"],
    }
    assert article_short_points(article) == [
        "New with tags — eBay £89.99 — Amazon £99.99"
    ]


def test_publication_fingerprint_changes_with_blogger_url():
    article = {"slug": "air-fryer", "source_sha": "v1", "title": "Air fryers"}
    first = publication_fingerprint(article, "https://example.com/one")
    second = publication_fingerprint(article, "https://example.com/two")
    assert first != second



def test_headline_fit_never_exceeds_three_lines():
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (WIDTH, HEIGHT), "black")
    draw = ImageDraw.Draw(canvas)
    headline = (
        "Best Extremely Long Product Title Worth Buying in the UK "
        "for Families Who Want Better Value in 2026"
    )
    font, lines = _fit_font(
        draw,
        headline,
        TEXT_MAX_WIDTH,
        max_lines=3,
        start=78,
        minimum=48,
    )
    assert len(lines) <= 3
    assert all(
        draw.textbbox((0, 0), line, font=font)[2] <= TEXT_MAX_WIDTH
        for line in lines
    )


def test_short_slide_renders_centered_mobile_safe_layout(tmp_path):
    from PIL import Image, ImageDraw

    hero = tmp_path / "hero.jpg"
    logo = tmp_path / "logo.png"

    Image.new("RGB", (1600, 900), (120, 130, 140)).save(hero)
    logo_image = Image.new("RGBA", (600, 100), (255, 255, 255, 0))
    logo_draw = ImageDraw.Draw(logo_image)
    logo_draw.rectangle((10, 15, 590, 85), fill=(8, 47, 91, 255))
    logo_image.save(logo)

    slide = create_slide(
        hero,
        logo,
        accent="#ef233c",
        kicker="BUYING GUIDE",
        headline="Best Air Fryers Worth Buying in the UK",
        subtext="Compare the features that matter before you buy.",
        slide_number=1,
        slide_count=3,
        image_first=True,
    )

    assert slide.size == (1080, 1920)
