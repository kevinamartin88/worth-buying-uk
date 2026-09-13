from __future__ import annotations

import html
from datetime import datetime


def render_post(
    title: str,
    niche: dict,
    items: list[dict],
    disclosure: str,
    generated_at: datetime,
    marketplace: str,
) -> str:
    bits = [
        '<div style="max-width:900px;margin:0 auto;line-height:1.55">',
        f'<p><strong>Affiliate disclosure:</strong> {html.escape(disclosure)}</p>',
        f'<p>Updated {generated_at.strftime("%d %B %Y")} using current eBay search results. '
        'Prices and availability can change after publication, so always confirm the final price on eBay.</p>',
        f'<p><strong>What this page does:</strong> it filters current fixed-price UK listings for '
        f'{html.escape(niche["name"])}. Listings stay in eBay&apos;s returned order; this page does not '
        'claim that every item is the cheapest on the internet.</p>',
    ]

    if not items:
        bits.append(
            '<p><strong>No listings currently passed our quality filters.</strong> '
            'Rather than filling the page with weak offers, this page will be checked again automatically.</p>'
        )
    else:
        for idx, item in enumerate(items, start=1):
            bits.append(render_item(idx, item))

    bits.extend([
        '<hr>',
        '<p style="font-size:0.9em"><strong>How items are filtered:</strong> price ceiling, '
        'seller feedback, genuine eBay-returned promotional information when available, and '
        'our own observations of the same listing over time. Seller-provided or eBay-displayed '
        'reference prices are not presented as independently verified market prices.</p>',
        '</div>',
    ])
    return "\n".join(bits)


def render_item(idx: int, item: dict) -> str:
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

    parts = [
        '<section style="margin:28px 0;padding-bottom:24px;border-bottom:1px solid #ddd">',
        f"<h2>{idx}. {title}</h2>",
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

    link_label = f"Check current price and availability on eBay"
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
    symbol = "£" if currency == "GBP" else f"{currency or ''} "
    return f"{symbol}{number:,.2f}"
