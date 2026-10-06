import hashlib
import json
from unittest.mock import Mock

import pytest
from PIL import Image

from src import curated_visuals, ai_visuals
import repair_air_fryer_heroes as repair_module


def configure(tmp_path, monkeypatch):
    monkeypatch.setattr(curated_visuals, 'ROOT', tmp_path)
    source = tmp_path / 'assets/ai/backgrounds/reviewed.jpg'
    source.parent.mkdir(parents=True)
    Image.new('RGB', (1600, 900), 'white').save(source)
    record = {'path': str(source.relative_to(tmp_path)), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (tmp_path / 'assets/ai/curated-backgrounds.json').write_text(json.dumps({'uk:test-guide': record}))
    return source


def test_date_change_and_force_reuse_reviewed_photo_without_diffusion(tmp_path, monkeypatch):
    source = configure(tmp_path, monkeypatch)
    save, request = Mock(), Mock(side_effect=AssertionError('Diffusion must not run'))
    monkeypatch.setattr(ai_visuals, '_save_branded_image', save)
    monkeypatch.setattr(ai_visuals.requests, 'post', request)
    output = tmp_path / 'hero.jpg'
    for date, force in [('2026-10-07', False), ('2026-10-08', True)]:
        article = {'slug': 'test-guide', 'title': 'Air Fryers', 'hero_visual_revision': date}
        assert ai_visuals.generate_image(article, 'uk', output, '', '', force=force)
    assert save.call_count == 2
    request.assert_not_called()


def test_changed_reviewed_source_is_rejected(tmp_path, monkeypatch):
    source = configure(tmp_path, monkeypatch)
    source.write_bytes(b'unreviewed replacement')
    with pytest.raises(RuntimeError, match='source changed'):
        curated_visuals.curated_background({'slug': 'test-guide'}, 'uk')


def test_no_air_fryer_photo_never_falls_back_to_diffusion(tmp_path, monkeypatch):
    monkeypatch.setattr(curated_visuals, 'ROOT', tmp_path)
    request = Mock(side_effect=AssertionError('Diffusion must never run'))
    monkeypatch.setattr(ai_visuals.requests, 'post', request)
    article = {'slug': 'new-air-fryers-us', 'title': 'Air Fryers', 'content_html': '<p>No suitable photo</p>'}
    with pytest.raises(RuntimeError, match='refusing diffusion fallback'):
        ai_visuals.generate_image(article, 'us', tmp_path / 'output.jpg', 'account', 'token', force=True)
    request.assert_not_called()


def test_unrelated_articles_have_no_curated_override(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    assert curated_visuals.curated_background({'slug': 'other'}, 'uk') is None
    assert curated_visuals.curated_background({'slug': 'test-guide'}, 'us') is None


def test_new_air_fryer_articles_inherit_reviewed_source(tmp_path, monkeypatch):
    source = configure(tmp_path, monkeypatch)
    path = tmp_path / 'assets/ai/curated-backgrounds.json'
    config = json.loads(path.read_text())
    config['air-fryer-defaults'] = {'uk': config['uk:test-guide'], 'us': config['uk:test-guide']}
    path.write_text(json.dumps(config))
    for market in ('uk', 'us'):
        article = {'slug': f'new-air-fryers-{market}-2027'}
        assert curated_visuals.curated_background(article, market) == source
        assert 'curated-basket-source-v1' in ai_visuals._article_style_version(article)


@pytest.mark.parametrize('market', ['uk', 'us'])
def test_live_repair_changes_only_hero_and_preserves_body_and_permalink(market, monkeypatch):
    blogger = Mock()
    blogger.find_post_by_exact_title.return_value = {'id': '42'}
    old = '<div class="wb-article-hero"><img src="old-oven.jpg"></div><p>Prices and manual copy</p>'
    new = '<div class="wb-article-hero"><img src="reviewed.jpg"></div><p>Prices and manual copy</p>'
    monkeypatch.setattr(repair_module, 'backfill_hero_if_missing', lambda *args: (new, 'reviewed.jpg', True))
    url = 'https://site/original-post.html'
    blogger.get_post_or_none.side_effect = [{'url': url, 'content': old}, {'url': url, 'content': new}]
    repair_module.repair(market, blogger)
    blogger.update_post_content.assert_called_once_with('42', new)
    blogger.create_post.assert_not_called()
