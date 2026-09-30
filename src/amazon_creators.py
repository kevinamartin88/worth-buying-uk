from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests


TOKEN_ENDPOINTS = {
    "3.1": "https://api.amazon.com/auth/o2/token",
    "3.2": "https://api.amazon.co.uk/auth/o2/token",
    "3.3": "https://api.amazon.co.jp/auth/o2/token",
}

MARKETS = {
    "uk": {
        "marketplace": "www.amazon.co.uk",
        "partner_tag": "worthbuyin008-21",
        "currency": "GBP",
    },
    "us": {
        "marketplace": "www.amazon.com",
        "partner_tag": "worthbuyingus-20",
        "currency": "USD",
    },
}


@dataclass(frozen=True)
class AmazonOffer:
    title: str
    price: float
    currency: str
    url: str


class AmazonCreatorsClient:
    """Small, optional client for Amazon's OAuth-based Creators API."""

    _token_cache: dict[tuple[str, str], tuple[str, float]] = {}

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        credential_version: str,
        market: str,
        timeout: int = 20,
    ) -> None:
        if market not in MARKETS:
            raise ValueError(f"Unsupported Amazon market: {market}")
        if credential_version not in TOKEN_ENDPOINTS:
            raise ValueError("Amazon credential version must be 3.1, 3.2 or 3.3")
        self.client_id = client_id
        self.client_secret = client_secret
        self.credential_version = credential_version
        self.market = market
        self.timeout = timeout

    @classmethod
    def from_env(cls, market: str) -> AmazonCreatorsClient | None:
        client_id = os.getenv("AMAZON_CREATORS_CLIENT_ID", "").strip()
        client_secret = os.getenv("AMAZON_CREATORS_CLIENT_SECRET", "").strip()
        version = os.getenv("AMAZON_CREATORS_CREDENTIAL_VERSION", "").strip()
        if not client_id or not client_secret or not version:
            return None
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            credential_version=version,
            market=market,
        )

    def _access_token(self) -> str:
        cache_key = (self.client_id, self.credential_version)
        cached = self._token_cache.get(cache_key)
        now = time.time()
        if cached and cached[1] > now + 60:
            return cached[0]

        response = requests.post(
            TOKEN_ENDPOINTS[self.credential_version],
            json={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "creatorsapi::default",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Amazon Creators API token response did not contain an access token")
        expires_in = max(int(payload.get("expires_in") or 3600), 120)
        self._token_cache[cache_key] = (token, now + expires_in)
        return token

    def search_offers(self, keywords: str, item_count: int = 5) -> list[AmazonOffer]:
        config = MARKETS[self.market]
        response = requests.post(
            "https://creatorsapi.amazon/catalog/v1/searchItems",
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
                "x-marketplace": config["marketplace"],
            },
            json={
                "keywords": keywords,
                "partnerTag": config["partner_tag"],
                "marketplace": config["marketplace"],
                "itemCount": max(1, min(item_count, 10)),
                "resources": ["itemInfo.title", "offersV2.listings.price"],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        items = ((response.json().get("searchResult") or {}).get("items") or [])
        offers: list[AmazonOffer] = []
        for item in items:
            title = str(
                (((item.get("itemInfo") or {}).get("title") or {}).get("displayValue"))
                or ""
            ).strip()
            listings = ((item.get("offersV2") or {}).get("listings") or [])
            if not title or not listings:
                continue
            money = ((listings[0].get("price") or {}).get("money") or {})
            try:
                price = float(money.get("amount"))
            except (TypeError, ValueError):
                continue
            currency = str(money.get("currency") or "").upper()
            url = str(item.get("detailPageURL") or "").strip()
            if currency != config["currency"] or price <= 0 or not url:
                continue
            offers.append(AmazonOffer(title=title, price=price, currency=currency, url=url))
        return offers
