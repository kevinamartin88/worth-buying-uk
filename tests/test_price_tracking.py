import json
from datetime import datetime, date, timezone
from src.price_tracking import refresh_tracked_prices, valid_observations

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def test_rechecks_exact_listing_once_per_day(monkeypatch, tmp_path):
    path = tmp_path / 'history.json'
    path.write_text(json.dumps({'daily|uk|v1|123|0': {'article_slug': 'guide', 'observations': []}}))
    class Client:
        def get_item(self, item_id, affiliate_reference):
            assert item_id == 'v1|123|0' and affiliate_reference == 'guide'
            return {'itemId': item_id, 'price': {'value': '40', 'currency': 'GBP'}}
    assert refresh_tracked_prices(path, 'uk', Client(), now=NOW) == 1
    assert refresh_tracked_prices(path, 'uk', Client(), now=NOW) == 0
    assert len(json.loads(path.read_text())['daily|uk|v1|123|0']['observations']) == 1


def test_bad_currency_never_becomes_price_observation(tmp_path):
    path = tmp_path / 'history.json'
    path.write_text(json.dumps({'daily|uk|abc': {'observations': []}}))
    class Client:
        def get_item(self, item_id, **kwargs):
            return {'itemId': item_id, 'price': {'value': '40', 'currency': 'USD'}}
    assert refresh_tracked_prices(path, 'uk', Client(), now=NOW) == 0


def test_observations_reject_stale_future_mixed_and_duplicate_dates():
    rows = [{'date': '2026-10-03', 'price': 100, 'currency': 'GBP'},
            {'date': '2026-10-03', 'price': 99, 'currency': 'GBP'},
            {'date': '2026-10-04', 'price': 90, 'currency': 'USD'},
            {'date': '2026-10-06', 'price': 20, 'currency': 'GBP'}]
    entry = {'observations': rows}
    valid = valid_observations(entry, 'GBP', date(2026, 10, 5))
    assert len(valid) == 1 and valid[0]['price'] == 99
    assert not valid_observations(entry, 'GBP', date(2026, 11, 1))
    entry['tracking_status'] = 'ended'
    assert not valid_observations(entry, 'GBP', date(2026, 10, 5))
