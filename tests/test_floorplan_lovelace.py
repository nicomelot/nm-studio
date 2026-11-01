import unittest

from nm_bridge.floorplan_lovelace import generate
from nm_bridge.floorplan_publisher import publish
from nm_bridge.dashboard_publisher import PublishError


ARCHIVE = {"version": 1, "plans": [{"id": "piano_1", "name": "Ufficio",
          "background": "data:image/png;base64,abc", "points": [
              {"id": "l1", "kind": "light", "label": "Spot 1", "icon": "spot", "x": 20, "y": 30,
               "entity_id": "light.l1"},
              {"id": "l2", "kind": "light", "label": "Spot 2", "icon": "downlight", "x": 50, "y": 30,
               "entity_id": "light.l1"},
              {"id": "cover", "kind": "knx", "label": "Tapparella", "icon": "cover", "x": 70, "y": 70,
               "entity_id": "cover.t1"},
              {"id": "missing", "kind": "light", "label": "Scollegato", "x": 80, "y": 80,
               "entity_id": ""}]}]}
ENTITIES = [{"entity_id": "light.l1"}, {"entity_id": "cover.t1"}]


class FakeHA:
    def __init__(self):
        self.calls = []
        self.saved = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def call(self, method, **kw):
        self.calls.append(method)
        if method == "lovelace/dashboards/list":
            return []
        if method == "lovelace/config/save":
            self.saved = kw["config"]
        if method == "lovelace/config":
            return self.saved
        return None


class FloorplanLovelaceTests(unittest.TestCase):
    def test_repeated_lights_and_cover_are_native(self):
        doc = generate(ARCHIVE, ENTITIES)
        self.assertEqual(doc["summary"], {"views": 1, "interactive_points": 3, "warnings": 1})
        card = doc["dashboard"]["views"][0]["cards"][0]
        self.assertEqual(card["type"], "picture-elements")
        self.assertEqual(card["image"], ARCHIVE["plans"][0]["background"])
        self.assertEqual(card["elements"][0]["tap_action"], {"action": "toggle"})
        self.assertEqual(card["elements"][1]["entity"], "light.l1")
        self.assertEqual(card["elements"][2]["tap_action"], {"action": "more-info"})
        self.assertEqual(card["elements"][0]["style"], {"left": "20%", "top": "30%"})

    def test_missing_entities_are_never_clickable(self):
        doc = generate(ARCHIVE, [])
        self.assertEqual(doc["summary"]["interactive_points"], 0)
        self.assertEqual(doc["dashboard"]["views"], [])

    def test_create_only_after_explicit_confirmation(self):
        draft = generate(ARCHIVE, ENTITIES)
        payload = {"confirm": True, "title": "Mappe Ufficio", "url_path": "nm-studio-ufficio",
                   "expected_fingerprint": draft["fingerprint"]}
        fake = FakeHA()
        result = publish(payload, ARCHIVE, ENTITIES, client_factory=lambda: fake)
        self.assertTrue(result["created"])
        self.assertEqual(fake.calls, ["lovelace/dashboards/list", "lovelace/dashboards/create",
                                      "lovelace/config/save", "lovelace/config"])
        with self.assertRaisesRegex(PublishError, "Conferma"):
            publish({**payload, "confirm": False}, ARCHIVE, ENTITIES, client_factory=lambda: FakeHA())
        with self.assertRaisesRegex(PublishError, "Anteprima"):
            publish({**payload, "expected_fingerprint": "old"}, ARCHIVE, ENTITIES, client_factory=lambda: FakeHA())


if __name__ == "__main__":
    unittest.main()
