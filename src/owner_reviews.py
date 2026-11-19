"""Curated product-review evidence; seller feedback is never an owner review."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / 'automation' / 'owner_review_evidence.json'


def matching_evidence(item, market, *, evidence=None, today=None):
    """An optional, dated exact-model match; a broken row cannot hide later rows."""
    try:
        rows = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8')) if evidence is None else evidence
        title = ' '.join(str(item.get('title') or '').casefold().split())
        today = today or date.today()
        for entry in rows:
            try:
                if entry['market'] != market or not entry.get('title_patterns'):
                    continue
                if not all(re.search(pattern, title) for pattern in entry['title_patterns']):
                    continue
                if any(re.search(pattern, title) for pattern in entry.get('excluded_title_patterns', [])):
                    continue
                if not date.fromisoformat(entry['reviewed_on']) <= today <= date.fromisoformat(entry['review_by']):
                    continue
                source = urlsplit(entry['source_url'])
                if source.scheme != 'https' or not source.hostname or source.username or source.password:
                    continue
                return entry
            except (ValueError, TypeError, KeyError, AttributeError, re.error):
                continue
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def product_comparison_html(items, market, *, evidence=None, today=None):
    """Compare supplied facts; no network requests and no product-quality score."""
    try:
        return _product_comparison_html(items, market, evidence=evidence, today=today)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return ''  # Optional presentation must never block the daily article.


def _product_comparison_html(items, market, *, evidence=None, today=None):
    if len(items) < 2:
        return ''
    esc = lambda value: html.escape(str(value), quote=True)
    rows = []
    for item in items[:6]:
        entry = matching_evidence(item, market, evidence=evidence, today=today) or {}
        aspects = {str(a.get('name') or '').casefold(): str(a.get('value') or '')
                   for a in item.get('localizedAspects') or [] if isinstance(a, dict)}
        # Merchant-declared aspects are labelled as such; never fill gaps with guessed specs.
        names = ['model', 'capacity', 'storage capacity', 'dimensions', 'voltage',
                 'power source', 'chuck size', 'battery included', 'number of batteries',
                 'speed settings', 'features', 'interface', 'form factor', 'material']
        details = '; '.join(f'{name.title()}: {aspects[name]}' for name in names if aspects.get(name))
        spec_source = entry.get('spec_source_url') or ''
        if entry.get('comparison_specs') and spec_source.startswith('https://'):
            details = str(entry['comparison_specs'])
        package = aspects.get('set includes') or aspects.get('items included') or aspects.get('included components')
        condition = item.get('condition') or 'Check listing condition'
        source_url = str(item.get('itemWebUrl') or '')
        source_parts = urlsplit(source_url)
        allowed = {'ebay.co.uk', 'www.ebay.co.uk'} if market == 'uk' else {'ebay.com', 'www.ebay.com'}
        source = (f'<a href="{esc(source_url)}" rel="sponsored nofollow" data-wb-retailer="ebay" '
                  'data-wb-placement="comparison-source">Listing details</a>'
                  if source_parts.scheme == 'https' and source_parts.hostname in allowed
                  and not source_parts.username and not source_parts.password else '')
        if spec_source.startswith('https://'):
            source += f' · <a href="{esc(spec_source)}">Product specifications</a>'
        cells = [esc(item.get('title') or 'Product'), esc(details or 'Compare the exact model specification on the listing'),
                 esc(package or 'Confirm the contents shown by this seller'), esc(condition), source]
        rows.append('<tr>' + ''.join('<td style="border:1px solid #dfe6ee;padding:10px;vertical-align:top">'+cell+'</td>' for cell in cells) + '</tr>')
    headings = ['Product', 'Specification differences', 'Included package', 'Condition', 'Sources']
    return ('<section class="wb-product-comparison"><h2>Compare the products side by side</h2>'
            '<p>Match the model, specification and included package before comparing price. '
            'Listing details are seller-stated; linked product specifications are identified separately. '
            'Seller feedback describes the transaction, not product performance.</p>'
            '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse"><thead><tr>'
            + ''.join(f'<th scope="col" style="text-align:left;padding:10px;background:#f6f8fb">{h}</th>' for h in headings)
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></section>')


def preserve_researched_guide(article, previous):
    """A scheduled refresh must not replace reviewed long-form copy with listing boilerplate."""
    if not isinstance(previous, dict) or not (previous.get('_research') or {}).get('preserve_editorial_body'):
        return article
    if previous.get('slug') != article.get('slug') or not previous.get('content_html'):
        return article
    result = dict(article)
    for key in ('title', 'content_html', '_seo', '_research', 'pinterest_title', 'pinterest_subtitle',
                'x_image_title', 'x_subtitle', 'x_text', 'youtube_short_points', '_monetisation'):
        if key in previous:
            result[key] = previous[key]
    result['_generator'] = {**article.get('_generator', {}), 'live_ebay_picks': False,
                            'pick_count': (previous.get('_research') or {}).get('models_compared', 0)}
    # Today's promotion token and the existing post slug remain owned by the normal generator.
    return result


def owner_review_html(item: dict, market: str, *, evidence=None, today=None) -> str:
    """Optional enrichment must never prevent the normal article from publishing."""
    try:
        return _owner_review_html(item, market, evidence=evidence, today=today)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error) as error:
        print(f'[owner-review-skip] Optional evidence unavailable: {type(error).__name__}')
        return ''


def _owner_review_html(item: dict, market: str, *, evidence=None, today=None) -> str:
    """Render only reviewed evidence for the exact model/variant being listed."""
    today = today or date.today()
    matched = matching_evidence(item, market, evidence=evidence, today=today)
    for entry in [matched] if matched else []:
        checked = date.fromisoformat(entry['reviewed_on'])
        expires = date.fromisoformat(entry['review_by'])
        if not checked <= today <= expires:
            continue
        source = urlsplit(entry['source_url'])
        if source.scheme != 'https' or not source.hostname or source.username or source.password:
            raise ValueError('Product-review evidence needs a public HTTPS source')
        kind = entry.get('source_kind', 'customer_reviews')
        labels = {
            'customer_reviews': ('What customers say', 'Customer experiences are individual reports; we have not independently tested this model.'),
            'social_discussion': ('What owners discuss', 'Public comments describe individual experiences; ownership has not been independently verified.'),
            'editorial_review': ('What reviewers found', 'This assessment draws on the linked reviewer’s published findings, not our own hands-on testing.'),
            'manufacturer_details': ('Features worth weighing up', 'These are manufacturer-stated features, not independently measured performance.'),
        }
        if kind not in labels:
            return ''
        heading, attribution = labels[kind]
        esc = lambda value: html.escape(str(value), quote=True)
        return (
            f'<section class="wb-owner-review" data-wb-review="{esc(entry["key"])}">'
            f'<h4>{esc(heading)}</h4>'
            f'<p>{esc(entry["praise"])}</p>'
            f'<p><strong>Before you choose:</strong> {esc(entry.get("before_buying", entry.get("limitations", "")))}</p>'
            f'<p><strong>Worth Buying take:</strong> {esc(entry["verdict"])}</p>'
            f'<p><small>Source: <a href="{esc(entry["source_url"])}">'
            f'{esc(entry["source_label"])}</a>. Evidence reviewed {checked.isoformat()}. '
            f'{esc(attribution)}'
            '</small></p></section>'
        )
    return ''
