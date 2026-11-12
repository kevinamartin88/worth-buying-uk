from src.public_urls import canonical_public_url
from src.internal_links import related_graph, update_discovery_links
from src.site_pages import article_topic, article_categories, TOPIC_TO_CLUSTER


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


def test_legacy_toaster_can_link_to_related_kitchen_guides_and_both_hubs():
    article = {'slug': 'best-toasters-worth-buying-uk-2026', 'title': 'Best Toasters Worth Buying'}
    topic = article_topic(article, article['slug'])
    assert topic == 'toasters'
    row = dict(slug=article['slug'], title=article['title'], topic=topic,
               cluster=TOPIC_TO_CLUSTER[topic], categories=article_categories(article),
               url='https://www.worthbuyinguk.co.uk/2026/09/toasters.html')
    blender = dict(slug='blenders', title='Best Blenders', topic='blenders',
                   cluster='Kitchen & Small Appliances', categories=['Home & Kitchen'],
                   url='https://www.worthbuyinguk.co.uk/2026/10/blenders.html')
    graph = related_graph([row, blender])
    assert [x['slug'] for x in graph[row['slug']]] == ['blenders']
    assert [x['slug'] for x in graph['blenders']] == [row['slug']]
    pages = {'cluster-kitchen-and-small-appliances': {'url': 'https://www.worthbuyinguk.co.uk/p/kitchen-small-appliances-buying-guides.html'},
             'category-home-and-kitchen': {'url': 'https://www.worthbuyinguk.co.uk/p/home-kitchen-buying-guides.html'}}
    original = '<p>Existing review copy.</p><a href="https://www.ebay.co.uk/itm/1?campid=3">Offer</a>'
    updated = update_discovery_links(original, row, graph[row['slug']], pages)
    assert updated.startswith(original)
    assert all(p['url'] in updated for p in pages.values())
    assert blender['url'] in updated
    assert update_discovery_links(updated, row, graph[row['slug']], pages) == updated


def test_topic_inference_keeps_explicit_topics_and_avoids_substring_matches():
    assert article_topic({'_generator': {'topic': 'tower-fans'}, 'title': 'Best fans'}) == 'tower-fans'
    assert article_topic({'title': 'A fantastic shopping checklist'}) == ''
    assert article_topic({'title': 'Best refurbished Apple Watch models'}) == 'smartwatches'
    assert article_topic({'title': 'Best Wi-Fi routers'}) == 'wifi-routers'
    assert article_topic({'title': 'How to compare prices before shopping'}) == ''
