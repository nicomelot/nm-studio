"""The Lovelace exporter must never create live controls for missing entities."""

import unittest

from nm_bridge.lovelace_generator import generate


class LovelaceGeneratorTests(unittest.TestCase):
    def sample(self):
        return {"version": 1, "project": "abc", "rooms": [], "structure": [
            {"id": "b", "type": "building", "parent": None, "name": "Magazzino", "active": True},
            {"id": "f", "type": "floor", "parent": "b", "name": "Terra", "active": True},
            {"id": "r", "type": "room", "parent": "f", "name": "Ufficio", "active": True}],
            "widgets": [
                {"type": "light", "name": "L1", "room": "Magazzino / Terra / Ufficio", "entity_id": "light.l1"},
                {"type": "cover", "name": "T1", "room": "Magazzino / Terra / Ufficio", "entity_id": ""}]}

    def test_native_tile_for_existing_entity_missing_only_in_report(self):
        result = generate(self.sample(), [{"entity_id": "light.l1"}])
        self.assertFalse(result["applied"])
        self.assertEqual(result["summary"], {"rooms": 1, "tiles": 1, "placeholders": 1})
        cards = result["dashboard"]["views"][0]["sections"][0]["cards"]
        self.assertEqual(cards[0], {"type": "tile", "entity": "light.l1", "name": "L1"})
        self.assertEqual(len(cards), 1)
        self.assertEqual(result["warnings"][0]["widget"], "T1")

    def test_unavailable_entity_is_not_exported_as_live_tile(self):
        result = generate(self.sample(), [])
        self.assertEqual(result["summary"]["tiles"], 0)
        self.assertEqual(result["summary"]["placeholders"], 2)

    def test_incompatible_entity_domain_is_reported_not_rendered(self):
        sample = self.sample()
        sample["widgets"][0]["entity_id"] = "sensor.l1"
        result = generate(sample, [{"entity_id": "sensor.l1"}])
        self.assertEqual(result["warnings"][0]["reason"], "Dominio HA incompatibile")

    def test_empty_layout_has_no_fake_controls(self):
        result = generate({"rooms": [], "structure": [], "widgets": []}, [])
        self.assertEqual(result["summary"]["tiles"], 0)
        self.assertEqual(result["dashboard"]["views"][0]["sections"], [])

    def test_cover_has_native_open_close_feature(self):
        sample = self.sample()
        sample["widgets"][1]["entity_id"] = "cover.t1"
        result = generate(sample, [{"entity_id": "light.l1"}, {"entity_id": "cover.t1"}])
        views = result["dashboard"]["views"]
        self.assertEqual([v["path"] for v in views],
                         ["panoramica", "illuminazione", "schermature", "ambienti"])
        cover_cards = views[2]["sections"][0]["cards"]
        self.assertEqual(cover_cards[0]["features"], [{"type": "cover-open-close"}])
        self.assertEqual(views[2]["sections"][0]["title"], "Terra · Ufficio")
        self.assertEqual(result["summary"]["tiles"], 2)  # Unique HA entities, not repeated views.

    def test_navigation_does_not_create_fake_cards_or_states(self):
        sample = self.sample()
        result = generate(sample, [{"entity_id": "light.l1"}])
        views = result["dashboard"]["views"]
        all_cards = [c for v in views for s in v["sections"] for c in s["cards"]]
        self.assertTrue(all(c["entity"] == "light.l1" for c in all_cards))
        self.assertFalse(any("state" in c for c in all_cards))
        self.assertEqual(result["summary"]["placeholders"], 1)


if __name__ == "__main__":
    unittest.main()
