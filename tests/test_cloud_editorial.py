import copy
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import cloud_editorial as c


def clock(day, hour=11):
    return datetime(2026, 10, day, hour, tzinfo=ZoneInfo("Europe/London"))


class CloudEditorialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(c, "ROOT", self.root)
        self.patch.start()
        self.state_patch = patch.object(c, "STATE", self.root / "state/cloud_editorial.json")
        self.state_patch.start()
        self.brief = {"key": "students", "review_by": "2027-01-01"}

    def tearDown(self):
        self.state_patch.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def builder(self, brief, market, picks, today):
        return {"slug": "students-" + market, "title": market, "content_html": "verified"}

    def test_weekly_is_one_per_market_and_not_before_wednesday(self):
        state = {}
        collect = lambda *args: ["verified listing"]
        hero = lambda *args: None
        c.weekly(clock(6), state, [self.brief], collect, self.builder, hero)
        self.assertFalse(state)
        c.weekly(clock(7), state, [self.brief], collect, self.builder, hero)
        saved = copy.deepcopy(state)
        c.weekly(clock(8), state, [self.brief], lambda *a: self.fail("duplicate lookup"), self.builder, hero)
        self.assertEqual(state, saved)
        self.assertEqual(len(list(self.root.glob("articles*/*.json"))), 2)

    def test_failed_market_does_not_advance_or_publish_fallback(self):
        def collect(brief, market, slug):
            if market == "uk":
                raise ValueError("no evidence")
            return ["verified"]
        state = {}
        c.weekly(clock(7), state, [self.brief], collect, self.builder, lambda *a: None)
        self.assertEqual(state["weekly"]["uk"]["status"], "blocked")
        self.assertNotIn("week", state["weekly"]["uk"])
        self.assertFalse((self.root / "articles/students-uk.json").exists())
        self.assertTrue((self.root / "articles-us/students-us.json").exists())

    def test_expired_evidence_does_not_call_retailers(self):
        state = {}
        brief = {**self.brief, "review_by": "2026-10-01"}
        c.weekly(clock(7), state, [brief], lambda *a: self.fail("expired brief"), self.builder)
        self.assertEqual(state["weekly"]["us"]["status"], "blocked")

    def test_wrong_currency_spares_and_unsubstantiated_adaptive_claims_rejected(self):
        item = {"title": "Adaptive easy grip spoon", "price": {"currency": "GBP"}, "itemId": "1", "conditionId": "1000", "image": {"imageUrl": "photo"}}
        group = {"match": "spoon", "specifics": "easy grip", "new_only": True}
        self.assertFalse(c.eligible(item, group, "uk"))
        item["localizedAspects"] = [{"name": "Features", "value": "Easy grip"}]
        self.assertTrue(c.eligible(item, group, "uk"))
        self.assertFalse(c.eligible(item, group, "us"))
        item["conditionId"] = "3000"
        self.assertFalse(c.eligible(item, group, "uk"))
        item["conditionId"] = "1000"
        item["title"] += " spares only"
        self.assertFalse(c.eligible(item, group, "uk"))

    def test_air_fryer_capacity_not_assumed(self):
        item = {"title": "Air fryer 4L", "itemId": "1", "price": {"currency": "USD"}, "image": {"imageUrl": "photo"}}
        group = {"match": "air fryer", "capacity": True}
        self.assertTrue(c.eligible(item, group, "us"))
        for title in ("Air fryer", "Air fryer 10L", "Air fryer 4L replacement basket"):
            self.assertFalse(c.eligible({**item, "title": title}, group, "us"))

    def test_tagged_links_stay_in_the_right_market(self):
        url = c.tagged_url("https://www.worthbuyingusa.com/guide?utm_source=old", "us")
        self.assertEqual(url.count("utm_source="), 1)
        self.assertIn("utm_content=us", url)
        with self.assertRaises(ValueError):
            c.tagged_url("https://www.worthbuyinguk.co.uk/guide", "us")

    def test_growth_preserves_slug_price_and_records_only_existing_published_guides(self):
        article = {"slug": "old-slug", "title": "Existing", "content_html": "Original £59 price and photos", "_generator": {"topic": "air-fryers"}}
        c.save(self.root / "articles/old-slug.json", article)
        c.save(self.root / "state/articles_published.json", {"old-slug": {"status": "published", "url": "https://www.worthbuyinguk.co.uk/old", "source_file": "old-slug.json"}})
        state = {}
        c.growth(clock(5), state)
        updated = c.load(self.root / "articles/old-slug.json")
        self.assertEqual(updated["slug"], "old-slug")
        self.assertTrue(updated["content_html"].startswith(article["content_html"]))
        c.growth(clock(6), state)
        self.assertEqual(updated, c.load(self.root / "articles/old-slug.json"))
        self.assertIn("Only 1", state["warnings"]["uk"])

    def test_promotion_reservation_survives_unknown_outcome_and_prevents_repeat(self):
        state = {"growth": {"uk": {"s": {"title": "Guide", "source_file": "s.json"}}}}
        c.save(self.root / "articles/s.json", {"source_sha": "updated"})
        c.save(self.root / "state/articles_published.json", {"s": {"status": "published", "source_sha": "updated", "url": "https://www.worthbuyinguk.co.uk/guide"}})
        reserved = []
        class Client:
            def __init__(self, *args): pass
            def find_x_channel_id(self): return "UK"
            def create_post(self, **kwargs):
                self.assert_reserved()
                raise TimeoutError("unknown")
            def assert_reserved(self):
                assert reserved
        module = types.ModuleType("src.buffer")
        module.BufferClient = Client
        with patch.dict(sys.modules, {"src.buffer": module}), patch.dict("os.environ", {"BUFFER_API_KEY": "test"}):
            c.promote(clock(6), state, lambda s: reserved.append(copy.deepcopy(s)))
            self.assertEqual(state["promotions"]["uk"]["2026-10-06"]["status"], "outcome-unknown")
            c.promote(clock(6), state, lambda s: self.fail("duplicate reservation"))
            before = copy.deepcopy(state)
            c.promote(clock(20), state, lambda s: self.fail("experiment ended"))
            self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
