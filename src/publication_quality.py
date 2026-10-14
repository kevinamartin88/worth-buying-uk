"""Deterministic publication safeguards; no claims of rankings or GA4 receipt."""
from __future__ import annotations

import html
import re
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.seo import plain_text

CONFIG = {
    'uk': {'region': 'UK', 'ebay': 'ebay.co.uk', 'amazon': 'amazon.co.uk',
           'campid': '5339209132', 'mkrid': '710-53481-19255-0', 'siteid': '3',
           'tag': 'worthbuyin008-21', 'property': 'G-KL9MHT5ZJ1'},
    'us': {'region': 'USA', 'ebay': 'ebay.com', 'amazon': 'amazon.com',
           'campid': '5339209205', 'mkrid': '711-53200-19255-0', 'siteid': '0',
           'tag': 'worthbuyingus-20', 'property': 'G-EEYCNV01MN'},
}
ANCHOR = re.compile(r'<a\b[^>]*>', re.I)
HREF = re.compile(r'\bhref\s*=\s*([\"\'])(.*?)\1', re.I | re.S)
REL = re.compile(r'\brel\s*=\s*([\"\'])(.*?)\1', re.I | re.S)
STOP = {'the', 'a', 'an', 'in', 'for', 'and', 'with', 'best', 'worth', 'buying', 'uk', 'us', 'usa', 'guide', 'guides', 'current', 'offers', 'approved', 'retailers', 'review', 'reviews'}


def terms(value):
    return {word.rstrip('s') for word in re.findall(r'[a-z]{3,}', plain_text(value).casefold()) if word not in STOP}


@lru_cache(maxsize=2)
def duplicate_descriptions(market):
    counts = Counter()
    folder = Path(__file__).resolve().parents[1] / ('articles' if market == 'uk' else 'articles-us')
    for path in folder.glob('*.json'):
        try:
            article = json.loads(path.read_text(encoding='utf-8'))
            value = plain_text(str((article.get('_seo') or {}).get('description') or '')).casefold()
            if value:
                counts[value] += 1
        except (OSError, ValueError):
            continue
    return frozenset(value for value, count in counts.items() if count > 1)


def fit(value, limit=155):
    if len(value) <= limit:
        return value
    prefix = value[:limit - 1]
    return prefix.rsplit(' ', 1)[0].rstrip(' ,.;:-') + '…'


def choose_description(article, market, duplicates=()):
    supplied = plain_text(str((article.get('_seo') or {}).get('description') or ''))
    title = plain_text(str(article.get('title') or 'Product comparison'))
    body = plain_text(str(article.get('content_html') or '')).casefold()
    issues = []
    if not supplied:
        issues.append('missing description')
    else:
        if len(supplied) < 45 or len(supplied) > 170:
            issues.append('description length outside editorial range')
        region = r'\b(?:UK|United Kingdom)\b' if market == 'uk' else r'\b(?:USA|US|United States)\b'
        if not re.search(region, supplied, re.I):
            issues.append('missing regional context')
        wrong = r'\b(?:USA|United States)\b' if market == 'uk' else r'\b(?:UK|United Kingdom)\b'
        if re.search(wrong, supplied, re.I) and not re.search(wrong, title, re.I):
            issues.append('conflicting regional context')
        if not terms(title).intersection(terms(supplied)):
            issues.append('description does not identify the article topic')
        if re.search(r'https?://|\{[^}]*\}|\b(?:guaranteed|lowest price|number one|100% best)\b|[£$]\s*\d', supplied, re.I):
            issues.append('placeholder, price or unsupported promotional claim')
        if supplied.casefold() in duplicates:
            issues.append('description duplicated across articles')
        for feature in ['bluetooth', 'cellular', 'capacity', 'cleaning', 'warranty', 'milk', 'espresso']:
            if feature in supplied.casefold() and feature not in body:
                issues.append('description mentions a buying feature absent from the article')
                break
    if not issues:
        return fit(supplied), issues
    # Use the actual title and only buying checks mentioned in the article.
    clean_title = re.sub(r'\s*\(?20\d{2}\)?\s*$', '', title).strip(' .:-()')
    clean_title = re.sub(r'\s+worth buying(?:\s+in\s+the)?\s*(?:UK|USA|US)?', '', clean_title, flags=re.I).strip()
    clean_title = re.sub(r'\s+in\s+the\s+(?:UK|USA|US)$', '', clean_title, flags=re.I)
    checks = [label for keyword, label in [('compatib', 'compatibility'), ('capacity', 'capacity'),
              ('cleaning', 'cleaning'), ('warranty', 'warranty'), ('returns', 'returns'),
              ('retailer', 'retailer comparisons')] if keyword in body][:3]
    detail = ', '.join(checks) if checks else 'practical buying advice'
    selected = f'{fit(clean_title, 85)}: {CONFIG[market]["region"]} buying guide with {detail}.'
    return fit(selected), issues


def retailer_kind(url, market):
    try:
        parts = urlsplit(html.unescape(url))
        if parts.scheme not in {'http', 'https'}:
            return None
        host = (parts.hostname or '').casefold().removeprefix('www.')
    except ValueError:
        return None
    config = CONFIG[market]
    return 'ebay' if host == config['ebay'] else 'amazon' if host == config['amazon'] else None


def repair_affiliate_links(content, market, slug):
    config = CONFIG[market]
    def anchor(match):
        tag = match.group(0)
        href = HREF.search(tag)
        kind = retailer_kind(href.group(2), market) if href else None
        if not kind:
            return tag
        parts = urlsplit(html.unescape(href.group(2)))
        params = ({'mkcid': '1', 'mkrid': config['mkrid'], 'siteid': config['siteid'],
                   'campid': config['campid'], 'toolid': '20014', 'customid': slug[:256], 'mkevt': '1'}
                  if kind == 'ebay' else {'tag': config['tag']})
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.casefold() not in params]
        query.extend(params.items())
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        replacement = f'href={href.group(1)}{html.escape(url, quote=True)}{href.group(1)}'
        tag = tag[:href.start()] + replacement + tag[href.end():]
        rel = REL.search(tag)
        values = list(dict.fromkeys((html.unescape(rel.group(2)).split() if rel else []) + ['sponsored', 'nofollow']))
        replacement = 'rel="' + html.escape(' '.join(values), quote=True) + '"'
        return tag[:rel.start()] + replacement + tag[rel.end():] if rel else tag[:-1] + ' ' + replacement + '>'
    return ANCHOR.sub(anchor, content)


def affiliate_issues(links, market, slug):
    issues = []
    for index, link in enumerate(links):
        kind = retailer_kind(link['href'], market)
        if not kind:
            continue
        query = dict(parse_qsl(urlsplit(html.unescape(link['href'])).query, keep_blank_values=True))
        expected = {'campid': CONFIG[market]['campid'], 'customid': slug[:256]} if kind == 'ebay' else {'tag': CONFIG[market]['tag']}
        if any(query.get(key) != value for key, value in expected.items()):
            issues.append(f'{kind} link {index + 1}: incorrect affiliate attribution')
        if not {'sponsored', 'nofollow'}.issubset(set(link.get('rel', '').casefold().split())):
            issues.append(f'{kind} link {index + 1}: missing sponsored/nofollow qualification')
    return issues
