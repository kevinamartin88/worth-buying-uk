"""Curated product-review evidence; seller feedback is never an owner review."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

EVIDENCE_PATH = Path(__file__).resolve().parents[1] / 'automation' / 'owner_review_evidence.json'


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
    if evidence is None:
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
    title = ' '.join(str(item.get('title') or '').casefold().split())
    for entry in evidence:
        if market != entry['market']:
            continue
        if not all(re.search(pattern, title) for pattern in entry['title_patterns']):
            continue
        checked = date.fromisoformat(entry['reviewed_on'])
        expires = date.fromisoformat(entry['review_by'])
        if not checked <= today <= expires:
            continue
        source = urlsplit(entry['source_url'])
        if source.scheme != 'https' or not source.hostname or source.username or source.password:
            raise ValueError('Product-review evidence needs a public HTTPS source')
        esc = lambda value: html.escape(str(value), quote=True)
        return (
            f'<section class="wb-owner-review" data-wb-review="{esc(entry["key"])}">'
            '<h4>What customers say</h4>'
            f'<p>{esc(entry["praise"])}</p>'
            f'<p><strong>Limits of the feedback:</strong> {esc(entry["limitations"])}</p>'
            f'<p><strong>Worth Buying take:</strong> {esc(entry["verdict"])}</p>'
            f'<p><small>Product-review source: <a href="{esc(entry["source_url"])}">'
            f'{esc(entry["source_label"])}</a>. Evidence reviewed {checked.isoformat()}. '
            'Customer experiences are individual reports; we have not independently tested this model.'
            '</small></p></section>'
        )
    return ''
