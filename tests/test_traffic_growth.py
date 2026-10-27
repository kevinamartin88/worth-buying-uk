from src.traffic_growth import (
    buyer_fit_copy,
    ctr_description,
    ctr_title,
    factual_pros_cons,
    pick_badges,
    traffic_opportunity_score,
    worth_buying_score,
)


def item(price, feedback=99.5, count=5000, condition="New"):
    return {
        "title": "Example Product",
        "condition": condition,
        "price": {"value": str(price), "currency": "GBP"},
        "seller": {"feedbackPercentage": feedback, "feedbackScore": count},
    }


def test_ctr_title_uses_current_shortlist_and_price_range():
    rows = [item(49), item(79), item(129)]
    assert ctr_title("Air Fryers", "UK", 2026, rows) == "3 Best Air Fryers UK 2026: Picks from £49–£129"
    description = ctr_description("Air Fryers", "UK", 2026, rows)
    assert "Amazon and eBay checks" in description
    assert len(description) <= 155


def test_pick_badges_and_scores_are_data_led():
    rows = [item(120, 99.9, 20000), item(60, 99.0, 2000), item(90, 98.5, 500)]
    flags = [True, False, False]
    labels = pick_badges(rows, flags)
    assert "Best overall" in labels
    assert "Best value" in labels
    scores = [worth_buying_score(row, rows, flags[i]) for i, row in enumerate(rows)]
    assert all(50 <= score <= 98 for score in scores)


def test_pros_cons_and_buyer_fit_do_not_claim_hands_on_testing():
    rows = [item(60), item(100), item(140)]
    pros, cons = factual_pros_cons(rows[0], rows, False)
    best_for, avoid_if = buyer_fit_copy(rows[0], False)
    joined = " ".join(pros + cons + [best_for, avoid_if]).lower()
    assert "tested" not in joined
    assert "amazon" in joined


def test_traffic_opportunity_rewards_seasonality_and_longer_intent():
    seasonal = traffic_opportunity_score(
        "air-fryers", 70, month=11,
        seasonal_keys=("air-fryers",),
        evergreen_keys=("air-fryers",),
        previously_covered=True,
        query="large family air fryer",
    )
    broad = traffic_opportunity_score(
        "tvs", 70, month=11,
        seasonal_keys=(),
        evergreen_keys=("tvs",),
        previously_covered=False,
        query="tv",
    )
    assert seasonal > broad
