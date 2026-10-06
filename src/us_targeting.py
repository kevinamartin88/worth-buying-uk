"""USA-only presentation and publication safeguards. Never convert retailer URLs or prices."""
from __future__ import annotations

import copy
import html
import re
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
from urllib.parse import urlsplit, urlunsplit
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

US_ORIGIN = 'https://www.worthbuyingusa.com'
US_HOSTS = {'www.worthbuyingusa.com', 'worthbuyingusa.com', 'worthbuyingusa.blogspot.com'}
WORDS = {
    'colour': 'color', 'colours': 'colors', 'organiser': 'organizer', 'organisers': 'organizers',
    'organise': 'organize', 'organised': 'organized', 'organising': 'organizing',
    'tyre': 'tire', 'tyres': 'tires', 'jewellery': 'jewelry', 'recognise': 'recognize',
    'recognises': 'recognizes', 'recognised': 'recognized', 'favourite': 'favorite',
    'favourites': 'favorites', 'centre': 'center', 'centres': 'centers',
    'litre': 'liter', 'litres': 'liters', 'metre': 'meter', 'metres': 'meters',
    'postcode': 'ZIP code', 'postcodes': 'ZIP codes', 'postal code': 'ZIP code',
    'boot space': 'trunk space', 'petrol': 'gasoline', 'aluminium': 'aluminum',
    'optimise': 'optimize', 'optimised': 'optimized', 'prioritise': 'prioritize',
    'prioritised': 'prioritized', 'licence': 'license', 'catalogue': 'catalog',
    'bargain hunting': 'deal hunting',
}
WORD_RE = re.compile(r'\b(' + '|'.join(map(re.escape, WORDS)) + r')\b', re.I)
US_MERCHANTS = {'amazon.com', 'ebay.com', 'iherb.com', 'sharperimage.com', 'walmart.com', 'target.com', 'bestbuy.com', 'homedepot.com', 'lowes.com', 'costco.com'}
UK_RE = re.compile(r'\b(?:UK|United Kingdom|Britain|British|GBP|VAT|pounds sterling|EUR|CAD|AUD|JPY)\b|[£€¥]', re.I)
URL_RE = re.compile(r'https?://[^\s<>"\']+', re.I)


def us_url(value: str) -> str:
    """Normalize known USA aliases only; reject cross-market or unrelated URLs."""
    parts = urlsplit(html.unescape(value))
    if (parts.scheme not in {'http', 'https'} or parts.hostname not in US_HOSTS
            or parts.username or parts.password or parts.port not in {None, 80, 443}):
        raise ValueError(f'USA link must belong to WorthBuyingUSA: {value}')
    return urlunsplit(('https', 'www.worthbuyingusa.com', parts.path or '/', parts.query, parts.fragment))


def localize_text(value: str) -> str:
    def word(match):
        original = match.group()
        replacement = WORDS[original.casefold()]
        return replacement.upper() if original.isupper() else replacement.capitalize() if original[0].isupper() else replacement
    return WORD_RE.sub(word, value)


def validate_retailer(url: str) -> None:
    from urllib.parse import parse_qs, unquote
    parts = urlsplit(html.unescape(url))
    host = parts.hostname or ''
    if host in {'click.linksynergy.com', 'ad.linksynergy.com'}:
        target = (parse_qs(parts.query).get('murl') or [''])[0]
        if not target:
            raise ValueError('USA affiliate link requires an inspectable merchant destination')
        return validate_retailer(unquote(target))
    if (parts.scheme != 'https' or host.removeprefix('www.') not in US_MERCHANTS
            or parts.username or parts.password or parts.port not in {None, 443}):
        raise ValueError(f'Unapproved USA merchant: {host}')


class _RetailerLinks(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'sponsored' in (attrs.get('rel') or '').split():
            validate_retailer(attrs.get('href') or '')


def localize_html(value: str) -> str:
    # Preserve retailer URLs, scripts and styles. Add approximate US-unit
    # equivalents to numeric specifications while retaining source measurements.
    chunks = re.split(r'(<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)', value, flags=re.I | re.S)
    def units(text):
        text = localize_text(text)
        pattern = r'(?<![\w(])(-?\d+(?:\.\d+)?)\s*(liters?|L|cm|centimeters?|meters?|kg|kilograms?|°C|Celsius)\b'
        def convert(match):
            unit = match[2].casefold()
            value = float(match[1])
            if unit in {'°c', 'celsius'}:
                number, label = value * 9 / 5 + 32, '°F'
            elif unit in {'l', 'liter', 'liters'}:
                number, label = value * 1.056688, 'US quarts'
            elif unit in {'cm', 'centimeter', 'centimeters'}:
                number, label = value / 2.54, 'inches'
            elif unit in {'kg', 'kilogram', 'kilograms'}:
                number, label = value * 2.204623, 'lb'
            else:
                number, label = value * 3.28084, 'feet'
            return f'{number:.1f} {label} (approximately; {match[0]})'
        # Parentheses contain retained source specifications; skip those on
        # subsequent runs so publication and generation remain idempotent.
        sections = re.split(r'(\([^)]*\))', text)
        return ''.join(s if s.startswith('(') else re.sub(pattern, convert, s, flags=re.I) for s in sections)
    result = ''.join(chunk if chunk.startswith('<') else units(chunk) for chunk in chunks)
    def canonical(match):
        return us_url(match[0]) if urlsplit(match[0]).hostname in US_HOSTS else match[0]
    return URL_RE.sub(canonical, result)


def validate_us_copy(value: str, *, social: bool = False) -> None:
    _RetailerLinks().feed(value)
    visible = re.sub(r'<script\b.*?</script>|<style\b.*?</style>', '', value, flags=re.I | re.S)
    visible = html.unescape(re.sub(r'<[^>]+>', ' ', visible))
    if WORD_RE.search(visible) or UK_RE.search(visible):
        raise ValueError('USA copy contains British wording or non-USD currency')
    for raw in URL_RE.findall(html.unescape(value)):
        parts = urlsplit(raw.rstrip('.,);'))
        host = parts.hostname or ''
        if social:
            if host != 'www.worthbuyingusa.com' or parts.scheme != 'https':
                raise ValueError('USA social copy may link only to https://www.worthbuyingusa.com')
        elif (host.endswith(('.uk', '.gb')) or 'worthbuyinguk' in host
              or (('amazon.' in host or 'ebay.' in host) and host not in {'amazon.com', 'www.amazon.com', 'ebay.com', 'www.ebay.com'})
              or host in US_HOSTS and (host != 'www.worthbuyingusa.com' or parts.scheme != 'https')):
            raise ValueError(f'Non-US or noncanonical domain in USA copy: {host}')


def prepare_us_article(article: dict) -> dict:
    result = copy.deepcopy(article)
    fields = ('title', 'primary_category', 'hero_image_kicker', 'pinterest_title', 'pinterest_subtitle',
              'x_image_title', 'x_kicker', 'x_subtitle', 'x_text')
    for key in fields:
        if isinstance(result.get(key), str):
            result[key] = localize_text(result[key])
            validate_us_copy(result[key], social=key == 'x_text')
    for key in ('labels', 'youtube_short_points'):
        if key in result:
            result[key] = [localize_text(str(v)) for v in result[key]]
            for value in result[key]:
                validate_us_copy(value)
    if 'content_html' in result:
        result['content_html'] = localize_html(result['content_html'])
        if 'class="wb-us-shopping-context"' not in result['content_html']:
            result['content_html'] += ('\n<aside class="wb-us-shopping-context" lang="en-US">'
                '<p>Shopping in the United States: prices are in US dollars (USD). '
                'Check shipping to your ZIP code, applicable sales tax, and US warranty and return terms. '
                'Compare dimensions in inches or feet, weight in pounds, and temperatures in Fahrenheit. '
                'Manufacturer specifications may retain metric units; verify the exact model and '
                'US electrical compatibility where relevant.</p></aside>')
        validate_us_copy(result['content_html'])
    seo = result.setdefault('_seo', {})
    seo.update(language='en-US', target_country='US', site_url=US_ORIGIN + '/')
    for key in ('description', 'primary_keyword', 'authority_cluster'):
        if isinstance(seo.get(key), str):
            seo[key] = localize_text(seo[key]); validate_us_copy(seo[key])
    if 'secondary_keywords' in seo:
        seo['secondary_keywords'] = [localize_text(v) for v in seo['secondary_keywords']]
        for value in seo['secondary_keywords']:
            validate_us_copy(value)
    signal = seo.get('google_demand_signal')
    if signal and signal.get('geo') != 'US':
        raise ValueError('USA demand signal must explicitly use geo=US')
    return result


def us_article_output(func):
    """Apply the USA policy to shared builders while returning UK output unchanged."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        bound = signature(func).bind(*args, **kwargs)
        result = func(*args, **kwargs)
        return prepare_us_article(result) if bound.arguments.get('market') == 'us' and result is not None else result
    return wrapped


def us_audience_hours(now: datetime | None = None) -> bool:
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('America/New_York'))
    return 9 <= local.hour < 21
