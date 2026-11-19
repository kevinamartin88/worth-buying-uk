from datetime import date
import json

from src.owner_reviews import owner_review_html, EVIDENCE_PATH

TODAY = date(2026, 10, 13)


def test_exact_model_and_market_only():
    item = {'title': 'Tower 6.5L T16043GRY Slow Cooker'}
    result = owner_review_html(item, 'uk', today=TODAY)
    assert 'B&amp;Q' in result and 'What customers say' in result
    assert 'Before you choose' in result
    assert owner_review_html(item, 'us', today=TODAY) == ''
    assert owner_review_html({'title': 'Tower T16043BLK'}, 'uk', today=TODAY) == ''
    assert owner_review_html({'title': 'Tower T16043GRY2'}, 'uk', today=TODAY) == ''


def test_usa_variant_must_include_design_series_capacity_and_bag():
    title = 'Crock-Pot Design Series 7-Quart Cook & Carry Slow Cooker with Thermal Bag'
    result = owner_review_html({'title': title}, 'us', today=TODAY)
    assert 'individual experience' in result and 'pre-owned' in result
    assert 'Seller delivery feedback' not in result
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
    evidence[0]['source_kind'] = 'social_discussion'
    result = owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY)
    assert 'unverified ownership' in result
    assert 'What owners discuss' in result


def test_editorial_and_manufacturer_evidence_are_not_labelled_customer_reviews():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
    evidence[0]['source_kind'] = 'editorial_review'
    result = owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY)
    assert 'What reviewers found' in result and 'What customers say' not in result
    evidence[0]['source_kind'] = 'manufacturer_details'
    result = owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY)
    assert 'manufacturer-stated features' in result
    evidence[0]['source_kind'] = 'unsupported'
    assert owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=evidence, today=TODAY) == ''


def test_new_feedback_requires_exact_market_model_and_current_evidence():
    today = date(2026, 11, 19)
    assert 'chuck' in owner_review_html({'title': 'DeWalt DCD777C2 kit'}, 'us', today=today)
    assert owner_review_html({'title': 'DeWalt DCD777B bare tool'}, 'us', today=today) == ''
    assert owner_review_html({'title': 'DeWalt DCD777C2X kit'}, 'us', today=today) == ''
    assert owner_review_html({'title': 'DeWalt DCD777C2 kit'}, 'uk', today=today) == ''
    assert owner_review_html({'title': 'DeWalt DCD777C2 kit'}, 'us', today=date(2027, 2, 18)) == ''
    assert 'source' in owner_review_html({'title': 'Ring RTC2000'}, 'uk', today=today).lower()
    assert owner_review_html({'title': 'Ring RTC2000X'}, 'uk', today=today) == ''


def test_one_bad_evidence_row_does_not_hide_a_valid_match():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding='utf-8'))
    assert 'B&amp;Q' in owner_review_html({'title': 'Tower T16043GRY'}, 'uk', evidence=[{}, *evidence], today=TODAY)


def test_comparison_uses_listing_facts_without_turning_seller_rating_into_product_rating():
    from src.owner_reviews import product_comparison_html
    items = [
        {'title': 'Example Drill <script>', 'condition': 'New', 'seller': {'feedbackPercentage': '99.9'},
         'itemWebUrl': 'https://www.ebay.com/itm/123',
         'localizedAspects': [{'name': 'Voltage', 'value': '12 V'}, {'name': 'Set Includes', 'value': 'Battery & charger'}]},
        {'title': 'Another Drill', 'condition': 'Used', 'localizedAspects': [{'name': 'Voltage', 'value': '20 V'}]},
    ]
    result = product_comparison_html(items, 'us', evidence=[])
    assert '12 V' in result and '20 V' in result and 'Battery &amp; charger' in result
    assert '&lt;script&gt;' in result and '<script>' not in result
    assert '99.9' not in result and 'Best overall' not in result and 'WorthBuying score' not in result
    assert 'data-wb-retailer="ebay"' in result


def test_comparison_and_owner_feedback_fail_open_when_optional_research_is_missing(monkeypatch, tmp_path):
    import src.owner_reviews as reviews
    monkeypatch.setattr(reviews, 'EVIDENCE_PATH', tmp_path / 'missing.json')
    rows = [{'title': 'Unknown model one', 'condition': 'New'}, {'title': 'Unknown model two', 'condition': 'Used'}]
    assert reviews.owner_review_html(rows[0], 'uk') == ''
    result = reviews.product_comparison_html(rows, 'uk')
    assert 'Unknown model one' in result and 'Unknown model two' in result
    assert 'What customers say' not in result
    assert reviews.product_comparison_html([None, None], 'uk') == ''


def test_curated_guide_refresh_keeps_research_but_not_old_daily_promotion():
    from src.owner_reviews import preserve_researched_guide
    previous = {'slug': 'guide', 'title': 'Researched guide', 'content_html': '<p>Linked customer reports</p>',
                '_research': {'preserve_editorial_body': True, 'models_compared': 2},
                '_promotion': {'daily_featured_date': '2026-11-19'}, '_seo': {'description': 'Specific researched copy'}}
    fresh = {'slug': 'guide', 'title': 'Automatic listing list', 'content_html': '<p>Listings</p>',
             'source_sha': 'new-source', '_generator': {'market': 'uk', 'live_ebay_picks': True},
             '_promotion': {'daily_featured_date': '2026-11-20'}}
    result = preserve_researched_guide(fresh, previous)
    assert result['content_html'] == previous['content_html']
    assert result['_seo'] == previous['_seo']
    assert result['_promotion'] == fresh['_promotion'] and result['source_sha'] == 'new-source'
    assert result['slug'] == 'guide' and result['_generator']['pick_count'] == 2
    assert preserve_researched_guide(fresh, {**previous, 'slug': 'different'}) == fresh
