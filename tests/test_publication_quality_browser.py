"""Exercise the real metadata/listener JS in Chromium without live analytics."""
import pytest

from src.publication_quality import CONFIG
from src.publishing_seo import enrich_metadata
from verify_publication import PROBE, assess


@pytest.mark.parametrize('market,site', [('uk', 'www.worthbuyinguk.co.uk'), ('us', 'www.worthbuyingusa.com')])
def test_rendered_metadata_and_single_regionally_attributed_event(market, site):
    from playwright.sync_api import sync_playwright
    config = CONFIG[market]
    row = {'slug': 'fixture-coffee-guide', 'title': 'Compact Coffee Makers',
           'content_html': '<h2>Coffee makers</h2><p>Cleaning, warranty and retailer comparisons.</p>',
           '_seo': {'description': f'Compare compact coffee makers in the {config["region"]}: cleaning, warranty and retailer buying checks.'}}
    url = f'https://{site}/2026/10/coffee.html'
    body = row['content_html'] + f'<a href="https://www.{config["ebay"]}/itm/123">View listing</a>'
    enriched = enrich_metadata(body, row, market)
    # Installing the same guarded scripts twice must still yield one event.
    document = (f'<html><head><link rel="canonical" href="{url}">'
                f'<script>window.gtag=function(){{}};gtag("config","{config["property"]}");</script></head>'
                f'<body><div class="post-body">{enriched}{enriched}</div></body></html>')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            context.route('**/*', lambda route: route.abort())
            context.route(url, lambda route: route.fulfill(status=200, content_type='text/html', body=document))
            page = context.new_page()
            page.goto(url)
            data = page.evaluate(PROBE)
            result = assess(data, row, market, url)
            assert result['verification'] == 'passed', result['issues']
            assert len(data['events']) == 1
            assert data['events'][0][2]['send_to'] == config['property']
            assert data['events'][0][2]['article_slug'] == row['slug']
            # A genuinely duplicated listener is detected, rather than called a pass.
            page.evaluate('''() => document.addEventListener('click', () => window.gtag('event', 'wb_retailer_click', {article_slug:'fixture-coffee-guide'}))''')
            duplicate = assess(page.evaluate(PROBE), row, market, url)
            assert duplicate['verification'] == 'needs_attention'
            assert 'retailer click must produce exactly one event' in duplicate['issues']
            context.close()
        finally:
            browser.close()

