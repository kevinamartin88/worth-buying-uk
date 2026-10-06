"""Read CFS's current selling price from the primary product price block."""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlsplit

CFS_HOSTS = {"choicefurnituresuperstore.co.uk", "www.choicefurnituresuperstore.co.uk"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def cfs_destination(tracking_url):
    raw = (parse_qs(urlsplit(tracking_url).query).get("murl") or [""])[0]
    url = unquote(raw)
    parsed = urlsplit(url)
    return url if parsed.scheme == "https" and parsed.hostname in CFS_HOSTS else ""


def amount(raw):
    try:
        value = Decimal(raw.replace("£", "").replace(",", "").strip())
        return value if value.is_finite() and value > 0 and value == value.quantize(Decimal("0.01")) else None
    except (InvalidOperation, AttributeError):
        return None


class PriceBlock(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.visible, self.meta, self.currency, self.urls = [], [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        active = attrs.get("id") == "hideprice" or any(row[1] for row in self.stack)
        current = active and bool(set(attrs.get("class", "").split()) & {"pOne", "nowPrice"})
        if active:
            if tag == "meta":
                target = {"price": self.meta, "priceCurrency": self.currency}.get(attrs.get("itemprop"))
                if target is not None:
                    target.append(attrs.get("content", ""))
            if tag == "link" and attrs.get("itemprop") == "url":
                self.urls.append(attrs.get("href", ""))
        if tag not in VOID:
            self.stack.append((tag, active, current))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if any(row[2] for row in self.stack) and data.strip():
            self.visible.append(data.strip())


def price_from_cfs_page(document, final_url):
    parser = PriceBlock()
    parser.feed(document)
    visible = {amount(value) for value in parser.visible}
    metadata = {amount(value) for value in parser.meta}
    if (None in visible or None in metadata or len(visible) != 1 or visible != metadata
            or set(parser.currency) != {"GBP"}):
        return None
    target = urlsplit(final_url)
    if target.hostname not in CFS_HOSTS or not any(
        urlsplit(url).hostname in CFS_HOSTS and urlsplit(url).path.rstrip("/") == target.path.rstrip("/")
        for url in parser.urls
    ):
        return None
    return f"{next(iter(visible)):.2f}"


def checked_cfs_price(client, product):
    page = getattr(client, "_validated_product_pages", {}).get(product.url)
    return price_from_cfs_page(*page) if page else None
