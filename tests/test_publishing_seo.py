from src.publishing_seo import enrich_metadata, repair_metadata
from src.internal_links import related_graph, update_discovery_links
from src.site_pages import article_categories, CATEGORIES, category_key, build_pages


def test_metadata_repair_preserves_copy_and_is_idempotent():
    article = {'slug': 'test', 'title': 'Test', 'content_html': 'Generated',
               '_seo': {'description': 'Compare & choose </script> safely'}}
    class Client:
        post = {'id': '1', 'content': '<p>Manual copy</p>'}
        writes = 0
        def update_post_content(self, post_id, content):
            self.post['content'] = content
            self.writes += 1
        def get_post(self, post_id):
            return self.post
    client = Client()
    repair_metadata(client, client.post, article, 'uk')
    repair_metadata(client, client.post, article, 'uk')
    assert client.writes == 1
    assert client.post['content'].startswith('<p>Manual copy</p>')
    assert '</script> safely' not in client.post['content']
    assert '<meta ' not in client.post['content']


def test_reciprocal_graph_excludes_self_and_unrelated_guides():
    rows = [dict(slug=s, url='https://uk.test/' + s, title=t, categories=c)
            for s,t,c in [('old','Robot vacuums',['Cleaning']),
                          ('new','Cordless vacuums',['Cleaning']),
                          ('game','Gaming consoles',['Gaming'])]]
    graph = related_graph(rows)
    assert [r['slug'] for r in graph['old']] == ['new']
    assert [r['slug'] for r in graph['new']] == ['old']
    assert graph['game'] == []
    pages = {category_key('Cleaning'): {'url':'https://uk.test/p/cleaning'}}
    content = update_discovery_links('<p>Manual copy</p>', rows[0], graph['old'], pages)
    assert 'https://uk.test/p/cleaning' in content
    assert 'https://uk.test/new' in content
    assert content == update_discovery_links(content, rows[0], graph['old'], pages)


def test_all_six_hubs_and_uncategorised_gaming(monkeypatch):
    import src.site_pages as pages
    monkeypatch.setattr(pages, 'load_catalog', lambda market: [])
    keys = {p['key'] for p in build_pages('uk')}
    assert all(category_key(c) in keys for c in CATEGORIES)
    assert 'Gaming' in article_categories({'title':'Best gaming controllers'})
    assert 'Cleaning' in article_categories({'title':'Best pressure washers'})


def test_reciprocal_footers_stay_compact_and_skip_broad_home_matches():
    rows = [dict(slug=str(i), url='https://uk.test/' + str(i), title='Vacuum ' + str(i),
                 categories=['Cleaning'], checked=str(i)) for i in range(20)]
    assert all(len(links) <= 6 for links in related_graph(rows).values())
    rows = [dict(slug='washer', url='https://uk.test/washer', title='Pressure washers', categories=['Home & Kitchen']),
            dict(slug='wardrobe', url='https://uk.test/wardrobe', title='Wardrobe offers', categories=['Home & Kitchen'])]
    assert related_graph(rows)['washer'] == []
