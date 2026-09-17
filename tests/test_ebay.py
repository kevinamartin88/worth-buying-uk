from __future__ import annotations

from src.ebay import EbayClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"access_token": "test-token", "expires_in": 7200})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if "/item_summary/search" in url:
            return FakeResponse({"itemSummaries": [{"itemId": "v1|123|0"}]})
        return FakeResponse({"itemId": "v1|123|0", "title": "Test item"})


def test_uk_search_and_get_item_use_oauth_and_epn(monkeypatch):
    monkeypatch.setenv("EBAY_ENV", "production")
    monkeypatch.setenv("EBAY_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EPN_CAMPAIGN_ID", "1234567890")
    session = FakeSession()
    client = EbayClient.for_market("uk", session=session)

    found = client.discover("air fryers", 500, "article-air-fryers", limit=1)

    assert found[0]["title"] == "Test item"
    assert len([call for call in session.calls if call[0] == "POST"]) == 1
    search_call = session.calls[1]
    detail_call = session.calls[2]
    assert "priceCurrency:GBP" in search_call[2]["params"]["filter"]
    assert search_call[2]["headers"]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"
    assert "affiliateCampaignId=1234567890" in search_call[2]["headers"]["X-EBAY-C-ENDUSERCTX"]
    assert detail_call[1].endswith("/v1%7C123%7C0")
    assert detail_call[2]["headers"]["Authorization"] == "Bearer test-token"


def test_us_market_uses_usd_and_us_campaign(monkeypatch):
    monkeypatch.setenv("EBAY_ENV", "production")
    monkeypatch.setenv("EBAY_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EPN_US_CAMPAIGN_ID", "9876543210")
    session = FakeSession()
    client = EbayClient.for_market("us", session=session)

    client.search("air fryers", 500, False, "us-air-fryers", 1)

    search_call = session.calls[1]
    assert "priceCurrency:USD" in search_call[2]["params"]["filter"]
    assert search_call[2]["headers"]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert "affiliateCampaignId=9876543210" in search_call[2]["headers"]["X-EBAY-C-ENDUSERCTX"]
