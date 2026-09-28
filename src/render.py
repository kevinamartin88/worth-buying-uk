from __future__ import annotations

import html
from datetime import datetime


MARKET_COPY = {
    "EBAY_GB": {"country": "UK", "ebay_name": "eBay UK", "shipping": "delivery and returns"},
    "EBAY_US": {"country": "US", "ebay_name": "eBay", "shipping": "shipping and returns"},
}


def render_post(
    title: str,
    niche: dict,
    items: list[dict],
    disclosure: str,
    generated_at: datetime,
    marketplace: str,
) -> str:
    market = MARKET_COPY.get(marketplace, MARKET_COPY["EBAY_GB"])
    topic = html.escape(niche["name"])
    bits = [
        '<div style="max-width:900px;margin:0 auto;line-height:1.55">',
        f'<p><strong>Affiliate disclosure:</strong> {html.escape(disclosure)}</p>',
        f'<p><strong>Last checked:</strong> {generated_at.strftime("%d %B %Y")}. We reviewed current '
        f'{html.escape(market["ebay_name"])} results for {topic}, then removed listings that did not '
        'meet the price and seller-quality rules below. Prices and availability can change, so confirm '
        f'the final price, {html.escape(market["shipping"])}, and item condition before buying.</p>',
        f'<p><strong>Our quick verdict:</strong> these are the current {html.escape(market["country"])} '
        f'listings for {topic} that best matched our published checks. This is a filtered shortlist, not '
        'a claim that every item is the cheapest or best choice for every buyer.</p>',
        '<h2>How to choose</h2>',
        f'<p>Compare the exact specification and condition you need, the seller&apos;s recent feedback, '
        f'total delivered cost, and the return window. For {topic}, a lower headline price is only useful '
        'when the listing includes the features and accessories you actually need.</p>',
    ]

    if not items:
        bits.append(
            '<p><strong>No listings currently passed our quality filters.</strong> '
            'Rather than filling the page with weak offers, this page will be checked again automatically.</p>'
        )
    else:
        bits.append('<h2>Current shortlist</h2>')
        for idx, item in enumerate(items, start=1):
            bits.append(render_item(idx, item, marketplace))

    bits.extend([
        '<h2>How we made this shortlist</h2>',
        '<p>We use live marketplace data as a discovery tool, then apply a price ceiling, '
        'seller feedback, genuine eBay-returned promotional information when available, and '
        'our own observations of the same listing over time. Seller-provided or eBay-displayed '
        'reference prices are not presented as independently verified market prices. We do not '
        'accept payment from sellers for inclusion.</p>',
        '<p><strong>What to check before ordering:</strong> read the full listing, confirm compatibility '
        'and condition, and review the seller&apos;s latest feedback and returns terms. If those details do '
        'not suit you, skip the listing even if its price looks attractive.</p>',
        '</div>',
    ])
    return "\n".join(bits)


def render_item(idx: int, item: dict, marketplace: str = "EBAY_GB") -> str:
    title = html.escape(item.get("title", "eBay listing"))
    price = item.get("price") or {}
    price_text = money(price.get("value"), price.get("currency"))
    image = ((item.get("image") or {}).get("imageUrl") or "").strip()
    url = item.get("itemAffiliateWebUrl") or item.get("itemWebUrl") or "#"
    seller = item.get("seller") or {}
    feedback_pct = seller.get("feedbackPercentage")
    feedback_score = seller.get("feedbackScore")
    evaluation = item.get("_evaluation") or {}
    marketing = item.get("marketingPrice") or {}

    original = marketing.get("originalPrice") or {}
    discount = evaluation.get("discount_percentage")
    market = MARKET_COPY.get(marketplace, MARKET_COPY["EBAY_GB"])

    parts = [
        '<section style="margin:28px 0;padding-bottom:24px;border-bottom:1px solid #ddd">',
        f"<h3>{idx}. {title}</h3>",
    ]

    if image:
        parts.append(
            f'<p><a rel="sponsored nofollow" href="{html.escape(url, quote=True)}">'
            f'<img src="{html.escape(image, quote=True)}" alt="{title}" '
            'style="max-width:320px;height:auto"></a></p>'
        )

    parts.append(f"<p><strong>Current eBay price:</strong> {html.escape(price_text)}</p>")

    if original.get("value") and discount:
        parts.append(
            f"<p>eBay currently shows an original/reference price of "
            f"{html.escape(money(original.get('value'), original.get('currency')))} "
            f"and a {discount:.0f}% promotional reduction on this listing.</p>"
        )

    observed_drop = evaluation.get("observed_drop_percentage")
    if observed_drop is not None and observed_drop >= 5:
        parts.append(
            f"<p>Our tracker has observed this same listing at a median price about "
            f"{observed_drop:.0f}% higher than its current price.</p>"
        )

    if feedback_pct is not None:
        seller_text = f"{feedback_pct}% positive feedback"
        if feedback_score is not None:
            seller_text += f" ({feedback_score} feedback score)"
        parts.append(f"<p><strong>Seller signal:</strong> {html.escape(seller_text)}</p>")

    reasons = evaluation.get("reasons") or []
    if reasons:
        parts.append(
            "<p><strong>Why it passed:</strong> "
            + html.escape(", ".join(reasons))
            + ".</p>"
        )

    link_label = f"Check current price and availability on {market['ebay_name']}"
    parts.append(
        f'<p><a rel="sponsored nofollow" href="{html.escape(url, quote=True)}">'
        f"<strong>{html.escape(link_label)}</strong></a></p>"
    )
    parts.append("</section>")
    return "\n".join(parts)


def money(value, currency) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "See listing"
    symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
    symbol = symbols.get(currency, f"{currency or ''} ")
    return f"{symbol}{number:,.2f}"
