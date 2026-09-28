from __future__ import annotations

import base64
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests


PRODUCT_SEARCH_URL = "https://api.linksynergy.com/productsearch/1.0"
TOKEN_URL = "https://api.linksynergy.com/token"
TRACKING_HOST_SUFFIXES = (".linksynergy.com", ".rakutenadvertising.com")


@dataclass(frozen=True)
class RakutenProduct:
    name: str
    merchant: str
    url: str
    price: str = ""
    currency: str = ""
    advertiser_id: str = ""


def _text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    if child is None:
        child = element.find(f"{{*}}{name}")
    return " ".join((child.text or "").split()) if child is not None else ""


def _safe_tracking_url(value: str) -> str:
    url = value.strip()
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return ""
    if not any(host == suffix[1:] or host.endswith(suffix) for suffix in TRACKING_HOST_SUFFIXES):
        return ""
    return url


def _normalise_query(query: str) -> str:
    # Rakuten Product Search rejects several punctuation characters. Keeping
    # only words, spaces and dots also prevents malformed query strings.
    return " ".join(re.sub(r"[^A-Za-z0-9. ]+", " ", query).split())[:160]


class RakutenClient:
    """Small, fail-closed client for Rakuten Advertising Product Search."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: str,
        currency: str,
        session: requests.Session | None = None,
    ):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.account_id = account_id.strip()
        self.currency = currency.upper()
        self.session = session or requests.Session()
        self._access_token = ""

    @classmethod
    def for_market(
        cls, market: str, session: requests.Session | None = None
    ) -> "RakutenClient | None":
        key = market.strip().lower()
        if key not in {"uk", "us"}:
            raise ValueError("market must be 'uk' or 'us'")
        prefix = f"RAKUTEN_{key.upper()}"
        client_id = os.getenv(f"{prefix}_CLIENT_ID", "").strip()
        client_secret = os.getenv(f"{prefix}_CLIENT_SECRET", "").strip()
        account_id = os.getenv(f"{prefix}_ACCOUNT_ID", "").strip()
        currency = "GBP" if key == "uk" else "USD"
        if not all((client_id, client_secret, account_id)):
            return None
        return cls(client_id, client_secret, account_id, currency, session=session)

    def _token(self) -> str:
        if self._access_token:
            return self._access_token

        token_key = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        response = self.session.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Bearer {token_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "password", "scope": self.account_id},
            timeout=30,
        )
        response.raise_for_status()
        token = str(response.json().get("access_token", "")).strip()
        if not token:
            raise RuntimeError("Rakuten token response did not contain an access token")
        self._access_token = token
        return token

    def search_one(self, query: str) -> RakutenProduct | None:
        clean_query = _normalise_query(query)
        if not clean_query:
            return None

        response = self.session.get(
            PRODUCT_SEARCH_URL,
            headers={"Authorization": f"Bearer {self._token()}"},
            params={"keyword": clean_query, "max": 20, "sort": "retailprice", "sorttype": "asc"},
            timeout=30,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)

        for item in root.findall(".//item") + root.findall(".//{*}item"):
            url = _safe_tracking_url(_text(item, "linkurl"))
            name = _text(item, "productname")
            merchant = _text(item, "merchantname")
            if not url or not name or not merchant:
                continue

            price_node = item.find("price")
            if price_node is None:
                price_node = item.find("{*}price")
            price = " ".join((price_node.text or "").split()) if price_node is not None else ""
            currency = price_node.attrib.get("currency", "").upper() if price_node is not None else ""

            # Do not present a foreign-currency product on either regional site.
            # Blank currency is allowed because some feeds omit it.
            if currency and currency != self.currency:
                continue

            return RakutenProduct(
                name=name,
                merchant=merchant,
                url=url,
                price=price,
                currency=currency,
                advertiser_id=_text(item, "mid"),
            )
        return None
