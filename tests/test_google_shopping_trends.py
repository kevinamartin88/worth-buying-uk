from __future__ import annotations

from src.google_shopping_trends import _averages, _score


def test_recent_average_uses_last_two_weeks():
    values = [10.0] * 28 + [30.0] * 14
    recent, prior = _averages(values)
    assert recent == 30.0
    assert prior == 10.0


def test_rising_product_scores_above_flat_equal_interest():
    anchor = [50.0] * 42
    flat = [50.0] * 42
    rising = [20.0] * 28 + [50.0] * 14

    flat_score = _score(flat, anchor)
    rising_score = _score(rising, anchor)

    assert rising_score["score"] > flat_score["score"]
    assert rising_score["shopping_momentum"] > 1.0


def test_zero_interest_does_not_score():
    signal = _score([0.0] * 42, [50.0] * 42)
    assert signal["score"] == 0.0


def test_rate_limit_keeps_recent_observations_and_stops_requests(monkeypatch, tmp_path):
    import requests
    from src import google_shopping_trends as shopping, shopping_cache as cache
    monkeypatch.setattr(cache, "CACHE_PATH", tmp_path / "cache.json")
    topics = [("air", "Air", "air purifier"), ("slow", "Slow", "slow cooker")]
    cache.remember("uk", [(topics[0], {"query": "air purifier", "score": 50})])
    calls = []
    def limited(*args):
        calls.append(True)
        response = requests.Response()
        response.status_code = 429
        raise requests.HTTPError(response=response)
    monkeypatch.setattr(shopping, "_explore_widgets", limited)
    assert shopping.rank_topics_by_google_shopping(topics, "uk")[0][0] == topics[0]
    assert cache.cooling_down("uk")
    assert shopping.rank_topics_by_google_shopping(topics, "uk")[0][1]["cached"]
    assert len(calls) == 1
