import json
from unittest.mock import Mock
from src import ai_visuals, curated_visuals
import repair_smartwatch_hero as repair_module

def test_smartwatch_refresh_reuses_reviewed_digital_source(tmp_path, monkeypatch):
    article = json.loads((curated_visuals.ROOT / 'articles-us/best-smartwatches-worth-buying-us.json').read_text())
    source = curated_visuals.curated_background(article, 'us')
    assert source.name == 'reviewed-digital-smartwatch.jpg'
    assert curated_visuals.configuration('uk', article['slug']) is None
    request = Mock(side_effect=AssertionError('Must not regenerate analog watches'))
    monkeypatch.setattr(ai_visuals.requests, 'post', request)
    save = Mock()
    monkeypatch.setattr(ai_visuals, '_save_branded_image', save)
    for force in (False, True):
        assert ai_visuals.generate_image(article, 'us', tmp_path / 'hero.jpg', '', '', force=force)
    assert save.call_count == 2
    request.assert_not_called()

def test_smartwatch_repair_preserves_existing_body_and_permalink(monkeypatch):
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = {'id': '42'}
    old = '<div class="wb-article-hero"><img src="analog.jpg"></div><p>Original product copy</p>'
    new = '<div class="wb-article-hero"><img src="smartwatch.jpg"></div><p>Original product copy</p>'
    monkeypatch.setattr(repair_module, 'backfill_hero_if_missing', lambda *args: (new, 'smartwatch.jpg', True))
    url = 'https://www.worthbuyingusa.com/2026/10/best-smartwatches-worth-buying-in-usa.html'
    blogger.get_post_or_none.side_effect = [{'url': url, 'content': old}, {'url': url, 'content': new}]
    repair_module.repair('us', blogger)
    blogger.update_post_content.assert_called_once_with('42', new)
    blogger.create_post.assert_not_called()
