from __future__ import annotations

from src.social_promotion import is_refreshed_daily_feature, needs_social_promotion


def test_new_article_is_socially_eligible():
    assert needs_social_promotion(None, {"promotion_token": "2026-10-06:us:new"}) is True


def test_same_daily_token_is_not_reposted():
    previous = {"promotion_token": "2026-10-06:us:air-fryers"}
    current = {"promotion_token": "2026-10-06:us:air-fryers"}
    assert needs_social_promotion(previous, current) is False


def test_refreshed_guide_is_reposted_on_new_daily_token():
    previous = {"promotion_token": "2026-10-05:us:air-fryers"}
    current = {"promotion_token": "2026-10-06:us:air-fryers"}
    assert needs_social_promotion(previous, current) is True
    assert is_refreshed_daily_feature(previous, current) is True


def test_legacy_article_without_daily_token_stays_suppressed():
    assert needs_social_promotion({"source_sha": "old"}, {"source_sha": "new"}) is False
