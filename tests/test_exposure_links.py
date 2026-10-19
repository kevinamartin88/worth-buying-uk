from src.public_urls import canonical_public_url
from src.internal_links import related_graph, update_discovery_links


def test_mobile_links_consolidate_without_touching_retailer_tracking():
    assert canonical_public_url('http://worthbuyingusa.blogspot.com/2026/10/a.html?m=1&utm_source=test#pick') == (
        'https://www.worthbuyingusa.com/2026/10/a.html?utm_source=test#pick')
    assert canonical_public_url('https://worthbuyinguk.co.uk/p/cleaning.html?m=0') == (
        'https://www.worthbuyinguk.co.uk/p/cleaning.html')
    for url in ['https://www.ebay.com/itm/123?m=1&campid=45',
                'https://www.worthbuyingusa.com.evil.test/a?m=1',
                'https://www.worthbuyinguk.co.uk:8443/a?m=1']:
        assert canonical_public_url(url) == url


def test_related_links_connect_complementary_guides_and_preserve_existing_body():
    topics = ['battery-chargers', 'jump-starters', 'tyre-inflators', 'dash-cams']
    catalog = [dict(slug=t, title=t.replace('-', ' '), topic=t, cluster='Motoring',
                    categories=['Motoring'], checked='2026-10-01',
                    url='https://www.worthbuyingusa.com/' + t + '.html?m=1') for t in topics]
    graph = related_graph(catalog)
    assert {r['topic'] for r in graph['battery-chargers']} >= {'jump-starters', 'tyre-inflators'}
    for slug, related in graph.items():
        assert all(slug in {r['slug'] for r in graph[other['slug']]} for other in related)
    body = '<p>Original review</p><a href="https://www.ebay.com/itm/1?m=1&campid=3">Offer</a>'
    updated = update_discovery_links(body, catalog[0], graph['battery-chargers'], {})
    assert body in updated
    assert '?m=1' not in updated[len(body):]
    assert update_discovery_links(updated, catalog[0], graph['battery-chargers'], {}) == updated
