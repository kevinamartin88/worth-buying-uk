import wave

from src.youtube_shorts import (
    SHORT_SECONDS,
    SLIDE_DURATIONS,
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
