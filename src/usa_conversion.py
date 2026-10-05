"""Evidence-based buying cards and optional GA4 measurement for USA guides."""
from __future__ import annotations

import html
import math
import re
from urllib.parse import urlsplit

from src.product_image_quality import product_image_html

PILOT_TOPICS = ('cordless-vacuums', 'ssds', 'slow-cookers', 'air-fryers', 'coffee-machines')
EXPERIMENT = 'usa-buying-cards-v1'


def relevant_product(title: str, query: str) -> bool:
    text = title.casefold()
    query = query.casefold()
    if not any(key in query for key in ('cordless vacuum', 'ssd', 'slow cooker', 'air fryer', 'coffee')):
        return True
    if 'ssd' in query and re.search(r'\d+\s*(?:pcs|pieces)\b', text):
        return False
    if re.search(r'\b(for parts|not working|faulty|broken|empty box|box only|manual only|'
                 r'replacement|accessories|accessory|filter only|charger only|cover|case|'
                 r'adapter|adapters|enclosure|heatsink|caddy)\b', text):
        return False
    rules = (
        ('cordless vacuum', r'\b(?:stick|upright|vacuum cleaner)\b', r'\b(?:car|mini|handheld only)\b'),
        ('ssd', r'\b(?:ssd|solid[- ]state)\b', r'\b(?:dummy|display only)\b'),
        ('slow cooker', r'\b(?:slow cooker|crock[- ]?pot)\b', r'\b(?:lid only|liner|liners|knob)\b'),
        ('air fryer', r'\bair fryer\b', r'\b(?:basket only|liner|liners|rack only)\b'),
        ('coffee', r'\b(?:coffee (?:maker|machine)|espresso (?:maker|machine))\b', r'\b(?:pod holder|pods only|filter basket|coffee grinder)\b'),
    )
    for key, required, excluded in rules:
        if key in query:
            return bool(re.search(required, text)) and not re.search(excluded, text)
    return True


def live_listing(item, now):
    """Details must affirm availability and a domestic USD fixed-price listing."""
    from datetime import datetime
    if item.get('listingMarketplaceId') != 'EBAY_US':
        return False
    if (item.get('itemLocation') or {}).get('country') != 'US':
        return False
    if 'FIXED_PRICE' not in (item.get('buyingOptions') or []):
        return False
    seller = item.get('seller') or {}
    try:
        price = float(item['price']['value'])
        if not math.isfinite(price) or price <= 0 or item['price']['currency'] != 'USD':
            return False
        if not 98 <= float(seller['feedbackPercentage']) <= 100 or int(seller['feedbackScore']) < 100:
            return False
        if item.get('itemEndDate') and datetime.fromisoformat(item['itemEndDate'].replace('Z', '+00:00')) <= now:
            return False
        stock = item.get('estimatedAvailabilities') or []
        if not stock or any(a.get('estimatedAvailabilityStatus') != 'IN_STOCK'
                            or (a.get('estimatedAvailableQuantity') is not None
                                and int(a['estimatedAvailableQuantity']) <= 0) for a in stock):
            return False
        url = urlsplit(str(item.get('itemWebUrl') or ''))
        return (url.scheme == 'https' and url.hostname in {'ebay.com', 'www.ebay.com'}
                and not url.username and not url.password and url.port in {None, 443}
                and url.path.startswith('/itm/'))
    except (KeyError, TypeError, ValueError):
        return False


def amazon_direct(offer):
    try:
        parts = urlsplit(str(offer.get('url') or ''))
        price = float(offer.get('price') or 0)
        return (parts.scheme == 'https' and parts.hostname in {'amazon.com', 'www.amazon.com'}
                and not parts.username and not parts.password and parts.port in {None, 443}
                and re.match(r'^/(?:dp|gp/product)/[A-Z0-9]{10}(?:/|$)', parts.path, re.I)
                and offer.get('currency') == 'USD' and math.isfinite(price) and price > 0)
    except (TypeError, ValueError):
        return False


def select_cards(items):
    remaining = list(items)
    selected = []
    if remaining:
        strongest = max(remaining, key=lambda i: (float((i.get('seller') or {}).get('feedbackPercentage') or 0),
                                                 int((i.get('seller') or {}).get('feedbackScore') or 0)))
        remaining.remove(strongest)
        selected.append(('Strong seller history', strongest))
    if remaining:
        lowest = min(remaining, key=lambda i: float(i['price']['value']))
        remaining.remove(lowest)
        label = ('Lowest checked listing price' if float(lowest['price']['value']) <= float(strongest['price']['value'])
                 else 'Another price to compare')
        selected.append((label, lowest))
    if remaining:
        new = next((i for i in remaining if str(i.get('condition') or '').casefold() == 'new'), None)
        selected.append(('New-condition alternative' if new else 'Another option to compare', new or remaining[0]))
    return selected


def shipping_text(item):
    values = []
    for option in item.get('shippingOptions') or []:
        cost = option.get('shippingCost') or {}
        try:
            value = float(cost['value'])
            if cost.get('currency') == 'USD' and math.isfinite(value) and value >= 0:
                values.append(value)
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return 'Shipping cost needs checking on eBay; sales tax may apply.'
    cost = min(values)
    return (f'Shipping from ${cost:.2f}; item plus shipping from '
            f'${float(item["price"]["value"]) + cost:.2f} before sales tax. Confirm delivery to your ZIP code.')


def tradeoff(item):
    condition = str(item.get('condition') or '').casefold()
    if any(term in condition for term in ('used', 'refurbished', 'open box', 'pre-owned')):
        return 'Condition and warranty can differ from a new retail unit; inspect the seller’s details.'
    return 'Check the exact model, included accessories, warranty and return terms before ordering.'


def retailer_link(url, label, retailer, placement, item_id):
    return (f'<a class="wb-retailer-button" href="{html.escape(url, quote=True)}" '
            'rel="sponsored nofollow" '
            f'data-wb-retailer="{retailer}" data-wb-placement="{placement}" '
            f'data-wb-item="{html.escape(str(item_id), quote=True)}" '
            'style="display:inline-block;padding:12px 16px;margin:6px 8px 6px 0;'
            'background:#082f5b;color:#fff!important;border-radius:8px;text-decoration:none;font-weight:700">'
            f'{html.escape(label)}</a>')


def cards_html(items, retailer_urls, query):
    cards = []
    for role, item in select_cards(items):
        title = str(item.get('title') or '')
        ebay, amazon, _ = retailer_urls(item, 'us', query)
        offer = item.get('_amazon_offer') or {}
        direct = amazon_direct(offer)
        if direct:
            amazon = offer['url']
        seller = item.get('seller') or {}
        specs = []
        for aspect in item.get('localizedAspects') or []:
            if str(aspect.get('name') or '').casefold() in {
                'brand', 'model', 'type', 'capacity', 'storage capacity', 'form factor',
                'interface', 'power', 'features', 'coffee type', 'number of cups',
            } and aspect.get('value'):
                specs.append(f'{aspect["name"]}: {aspect["value"]}')
        spec_html = '<p>' + html.escape(' · '.join(specs[:4])) + '</p>' if specs else ''
        photo = str((item.get('image') or {}).get('imageUrl') or '')
        links = retailer_link(ebay, 'Check this listing on eBay', 'ebay', 'quick-pick', item.get('itemId', ''))
        if direct:
            links += retailer_link(amazon, f'Check this model on Amazon — ${offer["price"]:.2f}', 'amazon', 'quick-pick', item.get('itemId', ''))
        else:
            # A search remains useful, but it must never look like an exact offer.
            links += (f'<p><a href="{html.escape(amazon, quote=True)}" rel="sponsored nofollow" '
                      'data-wb-retailer="amazon" data-wb-placement="search-alternative">'
                      'Search Amazon for alternatives</a> — exact match and price not verified.</p>')
        cards.append(
            '<article class="wb-buying-card" style="border:1px solid #dfe6ee;border-radius:14px;padding:18px;margin:16px 0">'
            f'<p><strong>{role}</strong></p><h3>{html.escape(title)}</h3>'
            + spec_html
            + (product_image_html(photo, title) if photo else '')
            + f'<p><strong>eBay listing price: ${float(item["price"]["value"]):.2f}</strong> · '
            f'{html.escape(str(item.get("condition") or "Check condition"))}</p>'
            f'<p>{html.escape(shipping_text(item))}</p>'
            f'<p><strong>Why compare it:</strong> seller feedback of {float(seller.get("feedbackPercentage") or 0):.1f}% '
            f'across {int(seller.get("feedbackScore") or 0):,} entries when checked.</p>'
            f'<p><strong>Before buying:</strong> {html.escape(tradeoff(item))}</p>{links}</article>'
        )
    return ('<section class="wb-usa-buying-cards"><h2>Three current options to compare</h2>'
            '<p>Start with the listing that suits your budget and condition preferences. '
            'These labels compare listing facts, not hands-on performance.</p>' + ''.join(cards) + '</section>')


def tracking_script(slug, measurement_id=''):
    """Use an existing GA4 tag, or load the explicitly configured USA property."""
    import json
    config = ''
    if measurement_id:
        if not re.fullmatch(r'G-[A-Z0-9]+', measurement_id):
            raise ValueError('Invalid GA4 Measurement ID')
        config = f"""
if (!window.gtag) {{
  window.dataLayer = window.dataLayer || [];
  window.gtag = function() {{ window.dataLayer.push(arguments); }};
  gtag('js', new Date());
  var tag = document.createElement('script'); tag.async = true;
  tag.src = 'https://www.googletagmanager.com/gtag/js?id={measurement_id}';
  document.head.appendChild(tag);
}}
gtag('config', '{measurement_id}');
"""
    return f"""<script class="wb-retailer-measurement">
(function() {{
  if (window.wbRetailerMeasurement) return;
  window.wbRetailerMeasurement = true;
  {config}
  document.addEventListener('click', function(event) {{
    var link = event.target.closest && event.target.closest('a[data-wb-retailer]');
    if (!link || typeof window.gtag !== 'function') return;
    var root = link.closest('[data-wb-article]');
    gtag('event', 'wb_retailer_click', {{
      article_slug: root ? root.getAttribute('data-wb-article') : {json.dumps(slug)},
      experiment_id: '{EXPERIMENT}', retailer: link.getAttribute('data-wb-retailer'),
      placement: link.getAttribute('data-wb-placement'),
      link_url: link.href, transport_type: 'beacon'
    }});
  }});
}})();
</script>"""
