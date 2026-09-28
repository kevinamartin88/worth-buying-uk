from datetime import datetime, timezone

from src.render import money, render_post
from src.seo import audit_post, meta_description


def sample_item(currency="GBP"):
    return {
        "title": "Example air fryer with viewing window",
        "price": {"value": "79.99", "currency": currency},
        "itemWebUrl": "https://www.ebay.example/item/1",
        "image": {"imageUrl": "https://img.example/air-fryer.jpg"},
        "seller": {"feedbackPercentage": "99.8", "feedbackScore": 1234},
        "_evaluation": {"reasons": ["strong seller feedback"]},
    }


def render(marketplace="EBAY_GB", currency="GBP"):
    return render_post(
        title="Best air fryers",
        niche={"name": "air fryers"},
        items=[sample_item(currency)],
        disclosure="We may earn a commission.",
        generated_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        marketplace=marketplace,
    )


def test_generated_post_passes_seo_checks_and_has_heading_hierarchy():
    content = render()
    assert audit_post(content) == []
    assert "<h2>Current shortlist</h2>" in content
    assert "<h3>1. Example air fryer" in content
    assert "eBay UK" in content


def test_us_copy_and_currency_are_localised():
    content = render("EBAY_US", "USD")
    assert "current US listings" in content
    assert "shipping and returns" in content
    assert "$79.99" in content
    assert money("12", "EUR") == "€12.00"


def test_meta_description_is_search_snippet_length():
    description = meta_description("Best air fryers", "<p>Useful guide.</p>", "EBAY_GB")
    assert len(description) <= 155
    assert description.startswith("Best air fryers")
