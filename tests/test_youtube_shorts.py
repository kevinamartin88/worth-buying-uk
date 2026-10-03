import wave

from PIL import Image, ImageDraw

from src.youtube_shorts import (
    HEIGHT,
    SHORT_SECONDS,
    SLIDE_DURATIONS,
    WIDTH,
    _short_background,
    _trim_logo,
    _write_retro_mall_music,
    article_short_points,
    deal_teaser,
    extract_short_points,
    publication_fingerprint,
    short_headline,
    short_description,
    short_title,
)


def test_landscape_hero_uses_image_side_instead_of_embedded_text_panel():
    source = Image.new("RGB", (1600, 900), "red")
    draw = ImageDraw.Draw(source)
    draw.rectangle((600, 0, 1599, 899), fill="blue")

    portrait = _short_background(source)

    assert portrait.size == (WIDTH, HEIGHT)
    assert portrait.getpixel((WIDTH // 2, HEIGHT // 2))[0] > 200
    assert portrait.getpixel((WIDTH // 2, HEIGHT // 2))[2] < 50


def test_clean_landscape_background_uses_product_centre():
    source = Image.new("RGB", (1600, 900), "red")
    draw = ImageDraw.Draw(source)
    draw.rectangle((650, 0, 950, 899), fill="green")

    portrait = _short_background(source, clean_source=True)

    centre = portrait.getpixel((WIDTH // 2, HEIGHT // 2))
    assert centre[1] > centre[0]


def test_logo_padding_is_trimmed_before_short_layout():
    logo = Image.new("RGBA", (1000, 1000), "white")
    draw = ImageDraw.Draw(logo)
    draw.rectangle((100, 430, 900, 570), fill="navy")

    trimmed = _trim_logo(logo)

    assert trimmed.width < 900
    assert trimmed.height < 300


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


def test_short_headline_removes_clutter_from_rakuten_title():
    article = {
        "title": "Current Dash Cams Offers from Approved USA Retailers (October 2026)"
    }

    assert short_headline(article) == "Dash Cams Deals Worth Checking"


def test_deal_teaser_uses_lowest_live_regional_price():
    article = {
        "content_html": (
            "<p>Price when checked: £139.99</p>"
            "<p>Price when checked: £119.99</p>"
        )
    }

    assert deal_teaser(article, "uk") == "Live offers from £119.99 when checked"


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
