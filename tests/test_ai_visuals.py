from PIL import Image, ImageDraw

from src import ai_visuals


def test_long_retailer_name_fits_inside_featured_card():
    draw = ImageDraw.Draw(Image.new("RGB", (800, 200), "white"))
    name = "Choice Furniture Superstore"

    font = ai_visuals._fit_single_line_font(
        draw,
        name,
        max_width=576,
        start_size=34,
        minimum_size=22,
    )

    assert ai_visuals._measure(draw, name, font)[0] <= 576


def test_truncated_choice_furniture_name_is_normalized_for_existing_articles():
    article = {"featured_retailer": "Choice Furniture Supersto"}

    assert ai_visuals._featured_retailer(article) == "Choice Furniture Superstore"
    assert ai_visuals._article_style_version(article).endswith("+choice-furniture-name-fit-v1")



def test_refresh_badge_uses_reader_friendly_date():
    article = {
        "_promotion": {
            "is_refresh": True,
            "daily_featured_date": "2026-10-06",
        }
    }
    assert ai_visuals._updated_badge_text(article) == "Updated 6 October"
    assert "updated-badge-v1-updated-6-october" in ai_visuals._article_style_version(article)


def test_new_article_has_no_updated_badge():
    article = {
        "_promotion": {
            "is_refresh": False,
            "daily_featured_date": "2026-10-06",
        }
    }
    assert ai_visuals._updated_badge_text(article) == ""
