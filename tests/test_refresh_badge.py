import io

import pytest
from PIL import Image, ImageDraw, ImageFont

import generate_pinterest_images as pinterest
import generate_pinterest_images_us as pinterest_us
import generate_x_images as x_images
from src import ai_visuals
from src.refresh_badge import updated_badge_text


@pytest.mark.parametrize("formatter", [
    updated_badge_text, ai_visuals._updated_badge_text,
    pinterest.updated_badge_text, pinterest_us.updated_badge_text,
    x_images.updated_badge_text,
])
@pytest.mark.parametrize("refresh, checked, expected", [
    (True, "2026-10-06", "Updated on 6 October 2026"),
    (True, "2025-09-30", "Updated on 30 September 2025"),
    (True, " 2024-02-29 ", "Updated on 29 February 2024"),
    (False, "2026-10-06", ""),
    (True, "", ""),
    (True, None, ""),
    (True, "2026-02-30", ""),
    (True, "not-a-date", ""),
])
def test_badge_uses_only_refresh_metadata(formatter, refresh, checked, expected):
    article = {
        "published": "2001-01-01",
        "_seo": {"last_checked_iso": "2002-02-02"},
        "_promotion": {"is_refresh": refresh, "daily_featured_date": checked},
    }
    assert formatter(article) == expected


def test_article_without_promotion_has_no_badge():
    assert updated_badge_text({}) == ""


def test_hero_style_changes_when_refresh_date_changes():
    article = {"_promotion": {"is_refresh": True, "daily_featured_date": "2026-10-06"}}
    original = ai_visuals._article_style_version(article)
    article["_promotion"]["daily_featured_date"] = "2027-10-06"
    assert ai_visuals._article_style_version(article) != original


@pytest.mark.parametrize("module", [ai_visuals, pinterest, pinterest_us, x_images])
@pytest.mark.parametrize("refresh", [True, False])
def test_social_render_draws_full_badge_inside_image(module, refresh, tmp_path, monkeypatch):
    # A real font catches clipping that Pillow's tiny fallback font would hide.
    def font(size, bold=False):
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                     "C:/Windows/Fonts/arialbd.ttf"):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        pytest.skip("No scalable test font available")

    monkeypatch.setattr(module, "_load_font" if module is ai_visuals else "load_font", font)
    recorded = []
    retailer_labels = []
    original = ImageDraw.ImageDraw.text

    def record(draw, xy, text, *args, **kwargs):
        if text.startswith("Updated"):
            recorded.append((text, draw.textbbox(xy, text, font=kwargs["font"])))
        if text == "FEATURED RETAILER":
            retailer_labels.append(draw.textbbox(xy, text, font=kwargs["font"]))
        return original(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    article = {"title": "A practical buying guide", "featured_retailer": "Example Store", "_promotion": {
        "is_refresh": refresh, "daily_featured_date": "2026-09-30",
    }}
    if module is ai_visuals:
        image = module._add_text_overlay(Image.new("RGB", (1600, 900)), article, "uk")
    elif module is x_images:
        image = Image.open(io.BytesIO(module.render(article, "uk")))
    else:
        output = tmp_path / "pin.png"
        module.render_article(article, output)
        image = Image.open(output)
    assert len(recorded) == int(refresh)
    if refresh:
        text, (left, top, right, bottom) = recorded[0]
        assert text == "Updated on 30 September 2026"
        assert 0 <= left < right <= image.width
        assert 0 <= top < bottom <= image.height
        if module in (pinterest, pinterest_us):
            assert 344 < top < bottom < 455
        if module is ai_visuals:
            assert retailer_labels[0][1] > bottom
