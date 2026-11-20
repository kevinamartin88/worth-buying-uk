from __future__ import annotations

import json

import pytest

import publish_articles
import publish_articles_us


class ExistingPostBlogger:
    def __init__(self) -> None:
        self.update_calls = []
        self.content = '<p><img src="https://blogger.test/manual-photo.jpg"></p>'

    def update_post_content(self, post_id, content):
        self.content = content

    def resolve_blog(self, expected_hosts, label):
        return {"id": "blog-1", "name": label}

    def find_post_by_exact_title(self, title):
        return {
            "id": "post-1",
            "title": title,
            "status": "LIVE",
            "url": "https://example.test/existing-post",
        }

    def get_post(self, post_id):
        return {
            "id": post_id,
            "title": "Manually edited title",
            "status": "LIVE",
            "url": "https://example.test/existing-post",
            "content": self.content,
        }

    def update_post(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))
        raise AssertionError("Reconciliation must not overwrite an existing Blogger post")

    def publish_post(self, post_id):
        raise AssertionError("An already-live reconciled post must not be republished")

    def create_post(self, *args, **kwargs):
        raise AssertionError("An existing Blogger post must not be duplicated")


@pytest.mark.parametrize("module,article_dir_name", [
    (publish_articles, "articles"),
    (publish_articles_us, "articles-us"),
])
def test_reconciliation_preserves_existing_blogger_content(
    monkeypatch, tmp_path, module, article_dir_name
):
    articles_dir = tmp_path / article_dir_name
    articles_dir.mkdir()
    article = {
        "slug": "existing-guide",
        "title": "Existing guide",
        "content_html": "<p>Generated replacement body</p>",
        "labels": ["Buying Guides"],
        "mode": "publish",
    }
    (articles_dir / "existing-guide.json").write_text(
        json.dumps(article), encoding="utf-8"
    )

    state_path = tmp_path / "state.json"
    blogger = ExistingPostBlogger()
    monkeypatch.setattr(module, "ARTICLES_DIR", articles_dir)
    monkeypatch.setattr(module, "STATE_PATH", state_path)
    monkeypatch.setattr(module.BloggerClient, "from_env", lambda: blogger)
    monkeypatch.setattr(module, "add_required_hero", lambda content, **kw: (content, "https://blogger.test/manual-photo.jpg"))
    monkeypatch.setattr(module, "backfill_hero_if_missing", lambda content, **kw: (content, "https://blogger.test/manual-photo.jpg", False))
    if module is publish_articles:
        monkeypatch.setattr(module, "PINTEREST_DIR", tmp_path / "missing-pinterest")

    module.main()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["existing-guide"]["post_id"] == "post-1"
    assert blogger.update_calls == []
    assert 'manual-photo.jpg' in blogger.content
    assert 'Generated replacement body' not in blogger.content
    assert 'wb-published-seo' in blogger.content


@pytest.mark.parametrize('module,market',[(publish_articles,'uk'),(publish_articles_us,'us')])
def test_new_article_with_bad_products_still_publishes_once(monkeypatch,tmp_path,module,market):
    folder=tmp_path/'articles';folder.mkdir()
    row={'slug':'new-guide','title':'4 Best Streaming Devices','mode':'publish','labels':['Tech'],
         'content_html':'<h3>1. USB Power Cable Adapter for Fire TV Stick</h3><a rel="sponsored" href="https://www.ebay.com/itm/123">Buy</a>',
         '_generator':{'query':'streaming devices'},'_promotion':{'daily_featured_date':'2026-11-20','promotion_token':'stable-token'}}
    (folder/'guide.json').write_text(json.dumps(row),encoding='utf8')
    class Blogger:
        def __init__(self):self.post=None;self.created=0
        def resolve_blog(self,*args):return {'id':'blog'}
        def find_post_by_exact_title(self,*args):return None
        def create_post(self,title,content,labels,is_draft):
            assert not is_draft
            self.created+=1
            domain='www.worthbuyinguk.co.uk' if market=='uk' else 'www.worthbuyingusa.com'
            self.post={'id':'123','title':title,'content':content,'status':'LIVE','url':f'https://{domain}/2026/11/new-guide.html'}
            return self.post
        def get_post(self,*args):return self.post
        def get_post_or_none(self,*args):return self.post
        def update_post_content(self,post_id,content):self.post['content']=content;return self.post
    blogger=Blogger()
    monkeypatch.setattr(module,'ARTICLES_DIR',folder)
    monkeypatch.setattr(module,'STATE_PATH',tmp_path/'published.json')
    monkeypatch.setattr(module.BloggerClient,'from_env',lambda:blogger)
    monkeypatch.setattr(module,'add_required_hero',lambda content,**kw:('<img src="https://example.com/hero.jpg">'+content,'https://example.com/hero.jpg'))
    monkeypatch.setattr(module,'backfill_hero_if_missing',lambda content,**kw:(content,'https://example.com/hero.jpg',False))
    if market=='uk':monkeypatch.setattr(module,'PINTEREST_DIR',tmp_path/'missing')
    module.main()
    state=json.loads((tmp_path/'published.json').read_text())
    assert state['new-guide']['status']=='published'
    assert state['new-guide']['promotion_token']=='stable-token'
    assert 'USB Power Cable Adapter' not in blogger.post['content']
    assert 'links open searches' in blogger.post['content']
    assert 'wb_retailer_click' in blogger.post['content']
    assert ('worthbuyin008-21' if market=='uk' else 'worthbuyingus-20') in blogger.post['content']
    module.main()
    assert blogger.created==1
