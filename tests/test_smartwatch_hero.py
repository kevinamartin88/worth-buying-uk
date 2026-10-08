import json
from unittest.mock import Mock

import pytest

from src import ai_visuals, curated_visuals
import repair_smartwatch_hero as repair_module


@pytest.mark.parametrize(
    "market,article_path",
    [
        ("uk", "articles/best-smartwatches-worth-buying-uk.json"),
        ("us", "articles-us/best-smartwatches-worth-buying-us.json"),
    ],
)
def test_smartwatch_refresh_reuses_reviewed_digital_source(
    market, article_path, tmp_path, monkeypatch
):
    article = json.loads(
        (curated_visuals.ROOT / article_path).read_text(encoding="utf-8")
    )
    source = curated_visuals.curated_background(article, market)
    assert source.name == "reviewed-digital-smartwatch.jpg"
    config = curated_visuals.configuration(market, article["slug"])
    assert config is not None
    assert "no analog dial" in config["reviewed_subject"]

    request = Mock(side_effect=AssertionError("Must not regenerate analog watches"))
    monkeypatch.setattr(ai_visuals.requests, "post", request)
    save = Mock()
    monkeypatch.setattr(ai_visuals, "_save_branded_image", save)

    for force in (False, True):
        assert ai_visuals.generate_image(
            article, market, tmp_path / f"{market}-hero.jpg", "", "", force=force
        )

    assert save.call_count == 2
    request.assert_not_called()


@pytest.mark.parametrize(
    "market,url",
    [
        (
            "uk",
            "https://www.worthbuyinguk.co.uk/2026/10/best-smartwatches-worth-buying-in-uk.html",
        ),
        (
            "us",
            "https://www.worthbuyingusa.com/2026/10/best-smartwatches-worth-buying-in-usa.html",
        ),
    ],
)
def test_smartwatch_repair_preserves_existing_body_and_permalink(
    market, url, monkeypatch
):
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = {"id": "42"}
    old = (
        '<div class="wb-article-hero"><img src="analog.jpg"></div>'
        "<p>Original product copy</p>"
    )
    new = (
        '<div class="wb-article-hero"><img src="smartwatch.jpg"></div>'
        "<p>Original product copy</p>"
    )
    monkeypatch.setattr(
        repair_module,
        "backfill_hero_if_missing",
        lambda *args: (new, "smartwatch.jpg", True),
    )
    blogger.get_post_or_none.side_effect = [
        {"url": url, "content": old},
        {"url": url, "content": new},
    ]

    repair_module.repair(market, blogger)

    blogger.update_post_content.assert_called_once_with("42", new)
    blogger.create_post.assert_not_called()


@pytest.mark.parametrize("market", ["uk", "us"])
def test_smartwatch_default_applies_to_future_smartwatch_slugs(market):
    config = curated_visuals.configuration(
        market, "best-smartwatches-worth-buying-future-2027"
    )
    assert config is not None
    assert config["path"].endswith("reviewed-digital-smartwatch.jpg")
    assert "no analog dial" in config["reviewed_subject"]
