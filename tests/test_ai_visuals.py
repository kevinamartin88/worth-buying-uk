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
