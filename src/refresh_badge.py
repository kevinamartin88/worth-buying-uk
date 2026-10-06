from datetime import date


def updated_badge_text(article: dict) -> str:
    """Use the checked date of a refreshed article, never its publish date."""
    promotion = article.get("_promotion") or {}
    if not promotion.get("is_refresh"):
        return ""
    raw = str(promotion.get("daily_featured_date") or "").strip()
    try:
        value = date.fromisoformat(raw)
    except ValueError:
        # An unknown date cannot support a permanent, accurate update badge.
        return ""
    return f"Updated on {value.day} {value.strftime('%B %Y')}"
