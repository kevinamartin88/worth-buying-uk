from __future__ import annotations

from src.amazon_creators import AmazonCreatorsClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_creators_api_fetches_and_reuses_token(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/auth/o2/token"):
            return FakeResponse({"access_token": "secret-token", "expires_in": 3600})
        return FakeResponse(
            {
                "searchResult": {
                    "items": [
                        {
                            "detailPageURL": "https://www.amazon.co.uk/dp/ABC",
                            "itemInfo": {"title": {"displayValue": "Ninja AF400UK"}},
                            "offersV2": {
                                "listings": [
                                    {"price": {"money": {"amount": 149.99, "currency": "GBP"}}}
                                ]
                            },
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr("src.amazon_creators.requests.post", fake_post)
    AmazonCreatorsClient._token_cache.clear()
    client = AmazonCreatorsClient(
        client_id="id",
        client_secret="secret",
        credential_version="3.2",
        market="uk",
    )
    first = client.search_offers("Ninja AF400UK")
    second = client.search_offers("Ninja AF400UK")

    assert first[0].price == 149.99
    assert first[0].currency == "GBP"
    assert second == first
    assert sum(url.endswith("/auth/o2/token") for url, _ in calls) == 1
    assert calls[1][1]["headers"]["Authorization"] == "Bearer secret-token"
