from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests


APP_SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass(frozen=True)
class EbayMarket:
    marketplace: str
    delivery_country: str
    currency: str
    campaign_secret: str


MARKETS = {
    "uk": EbayMarket("EBAY_GB", "GB", "GBP", "EPN_CAMPAIGN_ID"),
    "us": EbayMarket("EBAY_US", "US", "USD", "EPN_US_CAMPAIGN_ID"),
}


class EbayClient:
    """Production-safe client for eBay Browse search and getItem.

    OAuth credentials are read only from the environment. They are never accepted
    as command-line arguments, included in URLs, or written to logs/files.
    """

    def __init__(
        self,
        marketplace: str,
        delivery_country: str,
        currency: Optional[str] = None,
        campaign_id: Optional[str] = None,
        mock: bool = False,
        mock_file: Optional[Path] = None,
        session: Optional[requests.Session] = None,
    ):
        self.marketplace = marketplace
        self.delivery_country = delivery_country
        self.currency = currency or {"EBAY_GB": "GBP", "EBAY_US": "USD"}.get(marketplace)
        if not self.currency:
            raise ValueError("currency is required for an unknown eBay marketplace")
        self.mock = mock
        self.mock_file = mock_file
        self.env = os.getenv("EBAY_ENV", "sandbox").strip().lower()
        if self.env not in {"sandbox", "production"}:
            raise ValueError("EBAY_ENV must be 'sandbox' or 'production'")

        self.client_id = os.getenv("EBAY_CLIENT_ID", "")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "")
        self.campaign_id = campaign_id if campaign_id is not None else os.getenv("EPN_CAMPAIGN_ID", "")

        if self.env == "production":
            self.api_base = "https://api.ebay.com"
        else:
            self.api_base = "https://api.sandbox.ebay.com"

        self.session = session or requests.Session()
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    @classmethod
    def for_market(cls, market: str, **kwargs) -> "EbayClient":
        """Build a UK or US client using the correct marketplace and EPN secret."""
        key = market.strip().lower()
        try:
            profile = MARKETS[key]
        except KeyError as exc:
            raise ValueError("market must be 'uk' or 'us'") from exc

        campaign_id = kwargs.pop("campaign_id", None)
        if campaign_id is None:
            campaign_id = os.getenv(profile.campaign_secret, "")
        return cls(
            marketplace=profile.marketplace,
            delivery_country=profile.delivery_country,
            currency=profile.currency,
            campaign_id=campaign_id,
            **kwargs,
        )

    def _get_app_token(self) -> str:
        if self.mock:
            return "mock-token"
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Missing EBAY_CLIENT_ID or EBAY_CLIENT_SECRET")

        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        auth = base64.b64encode(raw).decode("ascii")

        response = self.session.post(
            f"{self.api_base}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": APP_SCOPE,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        expires_in = max(int(payload.get("expires_in", 7200)), 60)
        self._token_expires_at = time.monotonic() + expires_in - 60
        return self._token

    def _browse_headers(self, affiliate_reference: str = "") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._get_app_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            "Accept": "application/json",
        }
        if self.campaign_id:
            context = f"affiliateCampaignId={self.campaign_id}"
            if affiliate_reference:
                context += f",affiliateReferenceId={affiliate_reference[:256]}"
            headers["X-EBAY-C-ENDUSERCTX"] = context
        return headers

    def search(
        self,
        query: str,
        max_price: float,
        require_free_shipping: bool,
        affiliate_reference: str,
        limit: int = 40,
    ) -> list[dict]:
        if self.mock:
            if not self.mock_file:
                return []
            return json.loads(self.mock_file.read_text(encoding="utf-8"))["itemSummaries"]

        filters = [
            "buyingOptions:{FIXED_PRICE}",
            f"deliveryCountry:{self.delivery_country}",
            f"price:[0..{max_price:.2f}]",
            f"priceCurrency:{self.currency}",
        ]
        if require_free_shipping:
            filters.append("maxDeliveryCost:0")

        response = self.session.get(
            f"{self.api_base}/buy/browse/v1/item_summary/search",
            headers=self._browse_headers(affiliate_reference),
            params={
                "q": query,
                "filter": ",".join(filters),
                "limit": min(max(int(limit), 1), 200),
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("itemSummaries", [])

    def get_item(self, item_id: str, affiliate_reference: str = "") -> dict:
        """Return current details for one Browse item ID."""
        if self.mock:
            if not self.mock_file:
                return {}
            items = json.loads(self.mock_file.read_text(encoding="utf-8"))["itemSummaries"]
            return next((item for item in items if item.get("itemId") == item_id), {})
        if not item_id:
            raise ValueError("item_id is required")

        response = self.session.get(
            f"{self.api_base}/buy/browse/v1/item/{quote(item_id, safe='')}",
            headers=self._browse_headers(affiliate_reference),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def discover(
        self,
        query: str,
        max_price: float,
        affiliate_reference: str,
        limit: int = 8,
        require_free_shipping: bool = False,
        enrich: bool = True,
    ) -> list[dict]:
        """Reusable UK/US article input: search, then optionally enrich via getItem."""
        summaries = self.search(
            query=query,
            max_price=max_price,
            require_free_shipping=require_free_shipping,
            affiliate_reference=affiliate_reference,
            limit=limit,
        )
        if not enrich:
            return summaries

        detailed = []
        for summary in summaries:
            item_id = summary.get("itemId")
            if not item_id:
                continue
            item = self.get_item(item_id, affiliate_reference)
            detailed.append({**summary, **item})
        return detailed
