from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import generate_discount_codes as discounts
from googleapiclient.errors import HttpError
from generate_discount_codes import DiscountOffer, render_page, select_offers


def offer(
    advertiser: str,
    description: str,
    *,
    code: str = "",
    starts: str = "2026-09-01",
    ends: str = "2026-10-31",
) -> DiscountOffer:
    return DiscountOffer(
        advertiser=advertiser,
        description=description,
        url="https://click.linksynergy.com/deeplink?id=safe",
        source="Test feed",
        code=code,
        start_date=starts,
        end_date=ends,
    )


def test_select_offers_removes_inactive_and_limits_each_retailer():
    offers = [
        offer("Expired", "Old deal", code="OLD", ends="2026-09-29"),
        offer("Future", "Later deal", code="LATER", starts="2026-10-02"),
        offer("Shop One", "Deal 1", code="ONE"),
        offer("Shop One", "Deal 2", code="TWO"),
        offer("Shop One", "Deal 3", code="THREE"),
        offer("Shop One", "Deal 4", code="FOUR"),
        offer("Shop Two", "Sale price"),
    ]

    selected = select_offers(offers, date(2026, 9, 30))

    assert {item.advertiser for item in selected} == {"Shop One", "Shop Two"}
    assert sum(item.advertiser == "Shop One" for item in selected) == 3
    assert selected[0].code


def test_render_page_contains_clean_codes_tracking_and_region():
    content = render_page(
        [offer("Example Shop", "Save 20%", code="SAVE20")],
        "uk",
        date(2026, 9, 30),
    )

    assert "Current discount codes and retailer offers for UK shoppers" in content
    assert "SAVE20" in content
    assert "Verified source: Test feed" in content
    assert 'rel="sponsored nofollow"' in content
    assert 'style="color:#fff!important;-webkit-text-fill-color:#fff!important">View offer</a>' in content
    assert ".post-body a.wb-code-button:visited" in content
    assert "-webkit-text-fill-color:#fff!important" in content
    assert "30 September 2026" in content


def test_render_empty_page_does_not_leave_old_codes_visible():
    content = render_page([], "us", date(2026, 9, 30))

    assert "No verified codes available this week" in content
    assert "USA shoppers" in content


def test_ebay_offers_require_real_api_discount_and_regional_link(monkeypatch):
    class FakeEbay:
        def search(self, **_kwargs):
            return [
                {
                    "itemId": "good",
                    "title": "Current discounted product",
                    "price": {"value": "80", "currency": "GBP"},
                    "marketingPrice": {
                        "originalPrice": {"value": "100", "currency": "GBP"},
                        "discountPercentage": "20",
                    },
                    "itemAffiliateWebUrl": "https://www.ebay.co.uk/itm/good",
                },
                {
                    "itemId": "wrong-region",
                    "title": "Wrong regional link",
                    "price": {"value": "80", "currency": "GBP"},
                    "marketingPrice": {
                        "originalPrice": {"value": "100", "currency": "GBP"},
                        "discountPercentage": "20",
                    },
                    "itemAffiliateWebUrl": "https://www.ebay.com/itm/wrong",
                },
                {
                    "itemId": "not-discounted",
                    "title": "Ordinary listing",
                    "price": {"value": "100", "currency": "GBP"},
                    "itemWebUrl": "https://www.ebay.co.uk/itm/plain",
                },
            ]

    monkeypatch.setattr(discounts.EbayClient, "for_market", lambda _market: FakeEbay())
    monkeypatch.setattr(discounts, "MAX_EBAY_SEARCHES", 1)

    offers = discounts.ebay_offers("uk")

    assert len(offers) == 1
    assert offers[0].advertiser == "eBay"
    assert "20% off" in offers[0].description
    assert offers[0].source == "eBay Browse API"


def forbidden_error() -> HttpError:
    response = MagicMock(status=403, reason="Forbidden")
    return HttpError(response, b'{"error":{"message":"forbidden"}}')


def test_refresh_emails_manual_package_when_all_blogger_writes_are_forbidden(monkeypatch):
    blogger = MagicMock()
    blogger.upsert_page.side_effect = forbidden_error()
    blogger.upsert_post.side_effect = forbidden_error()
    monkeypatch.setattr(discounts, "collect_offers", lambda _market: [offer("Shop", "Deal")])
    monkeypatch.setattr(discounts.BloggerClient, "from_env", lambda: blogger)
    emailed = MagicMock(return_value={"status": "MANUAL_PACKAGE", "url": "email:test.html"})
    monkeypatch.setattr(discounts, "send_manual_package", emailed)

    result = discounts.refresh_market("uk")

    emailed.assert_called_once()
    assert emailed.call_args.args[0] == "uk"
    assert emailed.call_args.args[2] == 1
    assert result["status"] == "MANUAL_PACKAGE"


def test_public_codes_keep_markets_separate_and_confirm_terms(monkeypatch):
    body = ("Free Standard Delivery over £50 FREEDELIVERY50 "
            "Get 20% Off Your First Order NEW20 Save 10% off orders over £50 GOLDGB "
            "Get 25% Off Your First Order NEW25 Save 10% off orders over $80 GOLDUS")
    response = MagicMock(text=body)
    monkeypatch.setattr(discounts.requests, "get", lambda *a, **k: response)
    assert {o.code for o in discounts.retailer_offers("uk")} == {"FREEDELIVERY50", "NEW20", "GOLDGB"}
    assert {o.code for o in discounts.retailer_offers("us")} == {"NEW25", "GOLDUS"}


def test_public_codes_removed_when_source_changes_or_code_only_in_script(monkeypatch):
    response = MagicMock(text='<script>Get 25% Off Your First Order NEW25 GOLDUS</script><p>Offer withdrawn</p>')
    monkeypatch.setattr(discounts.requests, "get", lambda *a, **k: response)
    assert discounts.retailer_offers("us") == []


def test_unavailable_public_sources_do_not_keep_old_codes_forever(monkeypatch):
    rows = [{"market": "us", "url": "https://www.iherb.com/info/sales-and-offers",
             "checked_date": "2000-01-01"}]
    monkeypatch.setattr(discounts.json, "loads", lambda _text: rows)
    def unavailable(*a, **k):
        raise discounts.requests.RequestException("unavailable")
    monkeypatch.setattr(discounts.requests, "get", unavailable)
    assert discounts.retailer_offers("us") == []
