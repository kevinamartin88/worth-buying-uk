from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests


APP_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayClient:
    def __init__(
        self,
        marketplace: str,
        delivery_country: str,
        mock: bool = False,
        mock_file: Optional[Path] = None,
    ):
        self.marketplace = marketplace
        self.delivery_country = delivery_country
        self.mock = mock
        self.mock_file = mock_file
        self.env = os.getenv("EBAY_ENV", "sandbox").strip().lower()
        if self.env not in {"sandbox", "production"}:
            raise ValueError("EBAY_ENV must be 'sandbox' or 'production'")

        self.client_id = os.getenv("EBAY_CLIENT_ID", "")
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "")
        self.campaign_id = os.getenv("EPN_CAMPAIGN_ID", "")

        if self.env == "production":
            self.api_base = "https://api.ebay.com"
        else:
            self.api_base = "https://api.sandbox.ebay.com"

        self._token = None

    def _get_app_token(self) -> str:
        if self.mock:
            return "mock-token"
        if self._token:
            return self._token
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Missing EBAY_CLIENT_ID or EBAY_CLIENT_SECRET")

        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        auth = base64.b64encode(raw).decode("ascii")

        response = requests.post(
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
        self._token = response.json()["access_token"]
        return self._token

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

        token = self._get_app_token()

        filters = [
            "buyingOptions:{FIXED_PRICE}",
            f"deliveryCountry:{self.delivery_country}",
            f"price:[0..{max_price:.2f}]",
            "priceCurrency:GBP",
        ]
        if require_free_shipping:
            filters.append("maxDeliveryCost:0")

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            "Accept": "application/json",
        }

        # Passing the EPN campaign ID causes Browse API results to contain
        # itemAffiliateWebUrl values. affiliateReferenceId is the EPN sub-ID/custom ID.
        if self.campaign_id:
            ctx = f"affiliateCampaignId={self.campaign_id},affiliateReferenceId={affiliate_reference}"
            headers["X-EBAY-C-ENDUSERCTX"] = ctx

        response = requests.get(
            f"{self.api_base}/buy/browse/v1/item_summary/search",
            headers=headers,
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
