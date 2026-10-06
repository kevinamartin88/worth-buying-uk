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
    assert ai_visuals._updated_badge_text(article) == "Updated on 6 October 2026"
    assert "updated-badge-v1-updated-on-6-october-2026" in ai_visuals._article_style_version(article)


def test_new_article_has_no_updated_badge():
    article = {
        "_promotion": {
            "is_refresh": False,
            "daily_featured_date": "2026-10-06",
        }
    }
    assert ai_visuals._updated_badge_text(article) == ""



def test_air_fryer_direction_forbids_ovens():
    article = {
        "title": "Best Air Fryers Worth Buying in the USA (2026)",
        "labels": ["Home & Kitchen", "Air Fryers", "USA"],
        "hero_image_kicker": "AIR FRYER GUIDE",
    }
    direction = ai_visuals._visual_direction(article)
    assert "basket-style countertop air fryer" in direction
    assert "pull-out drawer seam" in direction
    assert "built-in oven" in direction
    assert "toaster-oven shape" in direction
    assert "transparent or glass front panel" in direction
    assert "air-fryer-subject-v3" in ai_visuals._article_style_version(article)


def test_air_fryer_product_candidate_rejects_oven_and_uses_real_basket_photo():
    article = {
        "content_html": (
            '<img src="https://i.ebayimg.com/images/g/oven/s-l225.jpg" '
            'alt="Gourmia 14-Quart Air Fryer Oven Rotisserie Convection">'
            '<img src="https://i.ebayimg.com/images/g/basket/s-l225.jpg" '
            'alt="9.5 QT Dual Basket Air Fryer with Double Basket">'
        )
    }

    candidate = ai_visuals._air_fryer_product_candidate(article)

    assert candidate == (
        "https://i.ebayimg.com/images/g/basket/s-l1600.jpg",
        "9.5 QT Dual Basket Air Fryer with Double Basket",
    )


def test_air_fryer_product_candidate_returns_none_when_only_oven_products_exist():
    article = {
        "content_html": (
            '<img src="https://i.ebayimg.com/images/g/oven/s-l1600.jpg" '
            'alt="12L Air Fryer Oven with Rotisserie and French Door">'
        )
    }

    assert ai_visuals._air_fryer_product_candidate(article) is None


def test_air_fryer_negative_prompt_forbids_oven_forms():
    article = {
        "title": "Best Air Fryers Worth Buying in the USA (2026)",
        "labels": ["Air Fryers", "USA"],
    }
    prompt = ai_visuals.negative_prompt(article)
    assert "toaster oven" in prompt
    assert "glass door" in prompt
    assert "air fryer oven" in prompt
    assert "oven rack" in prompt
