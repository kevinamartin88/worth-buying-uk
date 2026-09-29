from src.youtube_shorts import (
    extract_short_points,
    publication_fingerprint,
    short_description,
    short_title,
)


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
    assert "affiliate links" in description
    assert "#Shorts" in description


def test_publication_fingerprint_changes_with_blogger_url():
    article = {"slug": "air-fryer", "source_sha": "v1", "title": "Air fryers"}
    first = publication_fingerprint(article, "https://example.com/one")
    second = publication_fingerprint(article, "https://example.com/two")
    assert first != second
