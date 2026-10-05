from __future__ import annotations

import base64
import html as html_lib
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlsplit

import requests


PRODUCT_SEARCH_URL = "https://api.linksynergy.com/productsearch/1.0"
COUPON_FEED_URL = "https://api.linksynergy.com/coupon/1.0"
TOKEN_URL = "https://api.linksynergy.com/token"
TRACKING_HOST_SUFFIXES = (".linksynergy.com", ".rakutenadvertising.com")
PRODUCT_MATCH_STOPWORDS = {"and", "for", "from", "the", "with", "set", "pack", "new"}
GENERIC_DESTINATION_PATHS = {"", "/", "/search", "/products", "/collections", "/category", "/categories"}
SOFT_ERROR_MARKERS = (
    "page not found",
    "product not found",
    "404 not found",
    "this page doesn't exist",
    "this page does not exist",
    "the page you requested could not be found",
)
UNAVAILABLE_MARKERS = (
    "this product is no longer available",
    "this product is unavailable",
    "product is no longer available",
    "\"available\":false",
    "\"available\": false",
)


@dataclass(frozen=True)
class RakutenProduct:
    name: str
    merchant: str
    url: str
    price: str = ""
    currency: str = ""
    advertiser_id: str = ""


@dataclass(frozen=True)
class RakutenCoupon:
    advertiser: str
    advertiser_id: str
    description: str
    url: str
    code: str = ""
    restriction: str = ""
    start_date: str = ""
    end_date: str = ""
    categories: tuple[str, ...] = ()
    promotion_types: tuple[str, ...] = ()


def _text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    if child is None:
        child = element.find(f"{{*}}{name}")
    return " ".join((child.text or "").split()) if child is not None else ""


def _texts(element: ET.Element, container_name: str) -> tuple[str, ...]:
    container = element.find(container_name)
    if container is None:
        container = element.find(f"{{*}}{container_name}")
    if container is None:
        return ()
    values: list[str] = []
    for child in list(container):
        value = " ".join("".join(child.itertext()).split())
        if value and value not in values:
            values.append(value)
    return tuple(values)


def _safe_tracking_url(value: str) -> str:
    url = value.strip()
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return ""
    if not any(host == suffix[1:] or host.endswith(suffix) for suffix in TRACKING_HOST_SUFFIXES):
        return ""
    return url


def _product_destination_url(tracking_url: str) -> str:
    """Return an inspectable retailer destination without clicking the affiliate link."""
    parts = urlsplit(tracking_url)
    query = parse_qs(parts.query)
    raw = (query.get("murl") or [""])[0].strip()
    if not raw:
        return ""
    destination = unquote(raw)
    dest = urlsplit(destination)
    host = (dest.hostname or "").casefold()
    if dest.scheme != "https" or not host or dest.username or dest.password:
        return ""
    if any(host == suffix[1:] or host.endswith(suffix) for suffix in TRACKING_HOST_SUFFIXES):
        return ""
    return destination


def _same_site(expected_host: str, final_host: str) -> bool:
    expected = expected_host.casefold().removeprefix("www.")
    final = final_host.casefold().removeprefix("www.")
    return expected == final or final.endswith("." + expected) or expected.endswith("." + final)


def _product_match_tokens(name: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[A-Za-z0-9]+", name.casefold()):
        if len(token) < 3 or token in PRODUCT_MATCH_STOPWORDS or token in tokens:
            continue
        tokens.append(token)
    return tokens


def _response_text(response) -> str:
    text = getattr(response, "text", "")
    if text:
        return str(text)
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="ignore")
    return str(content or "")


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

    def search(self, query: str, limit: int = 5) -> list[RakutenProduct]:
        clean_query = _normalise_query(query)
        if not clean_query or limit < 1:
            return []

        response = self.session.get(
            PRODUCT_SEARCH_URL,
            headers={"Authorization": f"Bearer {self._token()}"},
            params={"keyword": clean_query, "max": 20, "sort": "retailprice", "sorttype": "asc"},
            timeout=30,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)

        products: list[RakutenProduct] = []
        seen_urls: set[str] = set()
        for item in root.findall(".//item") + root.findall(".//{*}item"):
            url = _safe_tracking_url(_text(item, "linkurl"))
            name = _text(item, "productname")
            merchant = _text(item, "merchantname")
            if not url or not name or not merchant or url in seen_urls:
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

            seen_urls.add(url)
            products.append(
                RakutenProduct(
                    name=name,
                    merchant=merchant,
                    url=url,
                    price=price,
                    currency=currency,
                    advertiser_id=_text(item, "mid"),
                )
            )
            if len(products) >= limit:
                break
        return products

    def search_one(self, query: str) -> RakutenProduct | None:
        products = self.search(query, limit=1)
        return products[0] if products else None

    def validate_product_destination(
        self, product: RakutenProduct, timeout: int = 12
    ) -> tuple[bool, str, str]:
        """Fail closed unless the retailer page still resolves to the named product.

        Validation deliberately opens the decoded retailer murl rather than the
        Rakuten click URL, so automated checks do not create affiliate clicks.
        """
        destination = _product_destination_url(product.url)
        if not destination:
            return False, "affiliate link has no inspectable retailer murl destination", ""

        expected = urlsplit(destination)
        try:
            response = self.session.get(
                destination,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; WorthBuyingLinkValidator/1.0; "
                        "+https://www.worthbuyinguk.co.uk/)"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return False, f"retailer request failed: {type(exc).__name__}", ""

        final_url = str(getattr(response, "url", "") or destination)
        final = urlsplit(final_url)
        final_host = (final.hostname or "").casefold()
        expected_host = (expected.hostname or "").casefold()
        if final.scheme != "https" or not final_host:
            return False, "retailer resolved to an invalid destination", final_url
        if not _same_site(expected_host, final_host):
            return False, "retailer redirected to a different site", final_url

        path = (final.path or "/").rstrip("/") or "/"
        path_cf = path.casefold()
        if path_cf in GENERIC_DESTINATION_PATHS or any(
            marker in path_cf
            for marker in ("/search", "/collections/", "/category/", "/404", "/not-found", "/error")
        ):
            return False, "retailer resolved to a generic or error page", final_url

        headers = getattr(response, "headers", {}) or {}
        content_type = str(headers.get("Content-Type", "")).casefold()
        if content_type and "html" not in content_type:
            return False, "retailer destination was not an HTML product page", final_url

        document = html_lib.unescape(_response_text(response))
        document_cf = document.casefold()
        title_match = re.search(r"<title[^>]*>(.*?)</title>", document, re.I | re.S)
        title = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
        title = " ".join(html_lib.unescape(title).split())
        visible_sample = re.sub(r"<[^>]+>", " ", document[:250000])
        evidence = " ".join((title + " " + visible_sample).casefold().split())

        error_evidence = " ".join((title + " " + visible_sample[:50000]).casefold().split())
        if any(marker in error_evidence for marker in SOFT_ERROR_MARKERS):
            return False, "retailer returned a soft 404 or missing-product page", final_url
        if any(marker in document_cf for marker in UNAVAILABLE_MARKERS):
            return False, "retailer page marks the product unavailable", final_url

        tokens = _product_match_tokens(product.name)
        if tokens:
            hits = sum(1 for token in tokens if token in evidence)
            required = 1 if len(tokens) <= 2 else max(2, (len(tokens) + 1) // 2)
            if hits < required:
                return (
                    False,
                    f"retailer page does not match product title ({hits}/{len(tokens)} key terms found)",
                    final_url,
                )

        return True, "validated retailer product page", final_url

    def coupons(self, network: int, limit: int = 100) -> list[RakutenCoupon]:
        """Return approved-advertiser promotions from Rakuten's Coupon Feed.

        Network 1 is the US and network 3 is the UK. Links that are not Rakuten
        tracking URLs are discarded so a malformed feed cannot inject arbitrary
        destinations into either site.
        """
        if network not in {1, 3}:
            raise ValueError("Rakuten coupon network must be 1 (US) or 3 (UK)")
        if limit < 1:
            return []

        response = self.session.get(
            COUPON_FEED_URL,
            headers={"Authorization": f"Bearer {self._token()}"},
            params={
                "network": network,
                "resultsperpage": min(limit, 500),
                "pagenumber": 1,
            },
            timeout=30,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)

        offers: list[RakutenCoupon] = []
        seen: set[tuple[str, str, str]] = set()
        links = root.findall(".//link") + root.findall(".//{*}link")
        for item in links:
            url = _safe_tracking_url(_text(item, "clickurl"))
            advertiser = _text(item, "advertisername")
            description = _text(item, "offerdescription")
            code = _text(item, "couponcode")
            if code.casefold() in {"n/a", "na", "none", "no code required"}:
                code = ""
            key = (advertiser.casefold(), description.casefold(), code.casefold())
            if not url or not advertiser or not description or key in seen:
                continue
            seen.add(key)
            offers.append(
                RakutenCoupon(
                    advertiser=advertiser,
                    advertiser_id=_text(item, "advertiserid"),
                    description=description,
                    url=url,
                    code=code,
                    restriction=_text(item, "couponrestriction"),
                    start_date=_text(item, "offerstartdate"),
                    end_date=_text(item, "offerenddate"),
                    categories=_texts(item, "categories"),
                    promotion_types=_texts(item, "promotiontypes"),
                )
            )
            if len(offers) >= limit:
                break
        return offers
