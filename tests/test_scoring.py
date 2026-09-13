from src.scoring import evaluate_item


def good_item():
    return {
        "itemId": "x",
        "title": "Test product",
        "price": {"value": "50.00", "currency": "GBP"},
        "buyingOptions": ["FIXED_PRICE"],
        "seller": {"feedbackPercentage": "99.7", "feedbackScore": 15000},
        "marketingPrice": {
            "originalPrice": {"value": "80.00", "currency": "GBP"},
            "discountPercentage": "37.5",
        },
    }


def test_good_item_is_eligible():
    result = evaluate_item(
        item=good_item(),
        price_history={},
        max_price=100,
        min_seller_feedback_percent=97,
        min_seller_feedback_score=25,
    )
    assert result["eligible"] is True
    assert result["score"] >= 50


def test_bad_seller_is_rejected():
    item = good_item()
    item["seller"] = {"feedbackPercentage": "92.0", "feedbackScore": 5}
    result = evaluate_item(
        item=item,
        price_history={},
        max_price=100,
        min_seller_feedback_percent=97,
        min_seller_feedback_score=25,
    )
    assert result["eligible"] is False


def test_observed_drop_adds_signal():
    item = good_item()
    item.pop("marketingPrice", None)
    history = {
        "x": {
            "observations": [
                {"price": 70},
                {"price": 70},
                {"price": 65},
                {"price": 68},
            ]
        }
    }
    result = evaluate_item(
        item=item,
        price_history=history,
        max_price=100,
        min_seller_feedback_percent=97,
        min_seller_feedback_score=25,
    )
    assert result["eligible"] is True
    assert result["observed_drop_percentage"] > 20
