from __future__ import annotations

from statistics import median


def evaluate_item(
    item: dict,
    price_history: dict,
    max_price: float,
    min_seller_feedback_percent: float,
    min_seller_feedback_score: int,
) -> dict:
    """
    Produce a pass/fail quality score without changing eBay's item ordering.

    This deliberately avoids inventing prices or calling a seller-supplied
    strike-through price "historic market value". If eBay returns a real
    marketingPrice discount we use it as one signal, clearly labelled later.
    """
    price = _float((item.get("price") or {}).get("value"))
    if price is None:
        return _fail("Missing price")

    currency = (item.get("price") or {}).get("currency")
    if currency != "GBP":
        return _fail("Non-GBP item")

    if price > max_price:
        return _fail("Over niche price ceiling")

    buying_options = item.get("buyingOptions") or []
    if buying_options and "FIXED_PRICE" not in buying_options:
        return _fail("Not fixed price")

    seller = item.get("seller") or {}
    feedback_pct = _float(seller.get("feedbackPercentage"))
    feedback_score = _int(seller.get("feedbackScore"))

    if feedback_pct is not None and feedback_pct < min_seller_feedback_percent:
        return _fail("Seller feedback percentage too low")
    if feedback_score is not None and feedback_score < min_seller_feedback_score:
        return _fail("Seller feedback count too low")

    score = 20.0  # Base score for surviving the hard filters.
    reasons = []

    # Seller confidence: up to 20 points.
    if feedback_pct is not None:
        if feedback_pct >= 99.5:
            score += 14
            reasons.append("very strong seller feedback")
        elif feedback_pct >= 99.0:
            score += 11
            reasons.append("strong seller feedback")
        elif feedback_pct >= 98.0:
            score += 8
        else:
            score += 4

    if feedback_score is not None:
        if feedback_score >= 10_000:
            score += 6
        elif feedback_score >= 1_000:
            score += 5
        elif feedback_score >= 250:
            score += 3
        elif feedback_score >= 50:
            score += 1

    # eBay's returned marketing discount: up to 30 points.
    marketing = item.get("marketingPrice") or {}
    discount_pct = _float(marketing.get("discountPercentage"))
    if discount_pct is not None and discount_pct > 0:
        score += min(discount_pct, 30)
        reasons.append(f"{discount_pct:.0f}% eBay-listed discount")

    # Our own observed price change for the same listing: up to 25 points.
    history = (price_history.get(item.get("itemId"), {}) or {}).get("observations", [])
    historic_prices = [
        _float(obs.get("price"))
        for obs in history
        if _float(obs.get("price")) is not None
    ]
    observed_drop_pct = None
    if len(historic_prices) >= 3:
        typical = median(historic_prices)
        if typical > 0 and price < typical:
            observed_drop_pct = ((typical - price) / typical) * 100
            score += min(observed_drop_pct * 1.25, 25)
            if observed_drop_pct >= 5:
                reasons.append(f"{observed_drop_pct:.0f}% below this listing's observed median")

    # Small value signal: price comfortably below the configured ceiling.
    if max_price > 0:
        ratio = price / max_price
        if ratio <= 0.60:
            score += 5
        elif ratio <= 0.80:
            score += 3

    return {
        "eligible": True,
        "score": round(min(score, 100), 1),
        "reasons": reasons,
        "discount_percentage": discount_pct,
        "observed_drop_percentage": observed_drop_pct,
    }


def _fail(reason: str) -> dict:
    return {
        "eligible": False,
        "score": 0.0,
        "reasons": [reason],
        "discount_percentage": None,
        "observed_drop_percentage": None,
    }


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
