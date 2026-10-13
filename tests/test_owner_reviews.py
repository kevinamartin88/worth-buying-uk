from datetime import date
import json

from src.owner_reviews import owner_review_html, EVIDENCE_PATH

TODAY = date(2026, 10, 13)


def test_exact_model_and_market_only():
    item = {'title': 'Tower 6.5L T16043GRY Slow Cooker'}
    result = owner_review_html(item, 'uk', today=TODAY)
    assert 'B&amp;Q' in result and 'What customers say' in result
    assert 'Limits of the feedback' in result
    assert owner_review_html(item, 'us', today=TODAY) == ''
    assert owner_review_html({'title': 'Tower T16043BLK'}, 'uk', today=TODAY) == ''
    assert owner_review_html({'title': 'Tower T16043GRY2'}, 'uk', today=TODAY) == ''


def test_usa_variant_must_include_design_series_capacity_and_bag():
    title = 'Crock-Pot Design Series 7-Quart Cook & Carry Slow Cooker with Thermal Bag'
    result = owner_review_html({'title': title}, 'us', today=TODAY)
    assert 'Only two product reviews' in result
    assert 'pre-owned' in result and 'Seller delivery feedback' in result
    assert owner_review_html({'title': title.replace('7-Quart', '6-Quart')}, 'us', today=TODAY) == ''
    assert owner_review_html({'title': title.replace('with Thermal Bag', '')}, 'us', today=TODAY) == ''


def test_no_evidence_or_expired_evidence_adds_no_claims():
    item = {'title': 'Tower T16043GRY'}
    assert owner_review_html(item, 'uk', evidence=[], today=TODAY) == ''
    assert owner_review_html(item, 'uk', today=date(2026, 11, 14)) == ''
    assert owner_review_html(item, 'uk', today=date(2026, 10, 12)) == ''


def test_review_content_is_escaped_and_does_not_generate_ratings_schema():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
    evidence[0]['praise'] = '<script>bad()</script>'
    result = owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY)
    assert '<script>' not in result and '&lt;script&gt;' in result
    assert 'aggregateRating' not in result and 'application/ld+json' not in result


def test_bad_or_missing_evidence_cannot_block_publishing(monkeypatch, tmp_path):
    import src.owner_reviews as reviews
    path = tmp_path / 'optional.json'
    monkeypatch.setattr(reviews, 'EVIDENCE_PATH', path)
    assert owner_review_html({'title': 'Tower T16043GRY'}, 'uk', today=TODAY) == ''
    path.write_text('not json', encoding='utf-8')
    assert owner_review_html({'title': 'Tower T16043GRY'}, 'uk', today=TODAY) == ''
    assert owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=[{}], today=TODAY) == ''


def test_public_social_source_can_use_the_same_optional_renderer():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
    evidence[0]['source_url'] = 'https://www.reddit.com/r/example/comments/example/'
    evidence[0]['source_label'] = 'Public owner discussion (unverified ownership)'
    result = owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY)
    assert 'unverified ownership' in result
