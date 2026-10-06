from __future__ import annotations


def promotion_token(record: dict) -> str:
    return str(record.get("promotion_token") or "").strip()


def needs_social_promotion(previous: dict | None, current: dict) -> bool:
    if not previous:
        return True
    token = promotion_token(current)
    if not token:
        return False
    return str(previous.get("promotion_token") or "").strip() != token


def is_refreshed_daily_feature(previous: dict | None, current: dict) -> bool:
    return bool(previous) and needs_social_promotion(previous, current)
