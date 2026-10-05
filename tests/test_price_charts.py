from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src import price_charts


def test_chart_requires_three_real_days_and_renders_png(monkeypatch, tmp_path):
    monkeypatch.setattr(price_charts, 'ROOT', tmp_path)
    today = datetime.now(ZoneInfo('Europe/London')).date()
    entry = {'title': 'Example & Listing', 'observations': [
        {'date': (today - timedelta(days=2-i)).isoformat(), 'price': price, 'currency': 'GBP'}
        for i, price in enumerate([100, 100, 80])
    ]}
    assert price_charts.render_chart('daily|uk|123', {'observations': entry['observations'][:2]}, 'uk') is None
    path = price_charts.render_chart('daily|uk|123', entry, 'uk')
    assert path.read_bytes().startswith(b'\x89PNG')
    assert 'Example &amp; Listing' in price_charts.chart_html('daily|uk|123', entry, 'uk')
