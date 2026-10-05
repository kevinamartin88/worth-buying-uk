import json
from src import shopping_cache as cache


def test_cache_is_region_query_and_time_specific(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(cache.time, "time", lambda: 100000)
    topic = ("air", "Air", "air purifier")
    signal = {"query": "air purifier", "score": 50, "source": "google-trends-google-shopping"}
    cache.remember("uk", [(topic, signal)])
    assert cache.cached_topics([topic], "uk")[0][1]["cached"]
    assert not cache.cached_topics([topic], "us")
    assert not cache.cached_topics([("other", "Other", "slow cooker")], "uk")
    monkeypatch.setattr(cache.time, "time", lambda: 200000)
    assert not cache.cached_topics([topic], "uk")


def test_rate_limit_cooldown_expires(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(cache.time, "time", lambda: 100000)
    cache.remember("uk", [], rate_limited=True)
    assert cache.cooling_down("uk")
    assert not cache.cooling_down("us")
    monkeypatch.setattr(cache.time, "time", lambda: 100000 + cache.COOLDOWN + 1)
    assert not cache.cooling_down("uk")
