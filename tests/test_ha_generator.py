"""Ensure draft generation is conservative and deterministic."""

import unittest

from nm_bridge.ha_generator import generate, validate_evidence, object_bits


class HAGeneratorTests(unittest.TestCase):
    def test_light_and_dimmer(self):
        result = generate({"project": "a" * 64, "widgets": [
            {"type": "light", "name": "L1", "fields": {"command": "1/1/0", "feedback": "1/1/4"}},
            {"type": "dimmer", "name": 'Dimmer "L11"', "fields": {"command": "1/0/1", "brightness": "1/0/2", "brightness_feedback": "1/0/6", "relative": "1/0/3"}}]})
        self.assertEqual(result["counts"], {"light": 2, "cover": 0, "climate": 0})
        self.assertIn('state_address: "1/1/4"', result["yaml"])
        self.assertIn('brightness_address: "1/0/2"', result["yaml"])
        self.assertNotIn('1/0/3', result["yaml"])
        self.assertIn('Dimmer \\"L11\\"', result["yaml"])
        self.assertTrue(result["requires_installer_approval"])
        self.assertFalse(result["applied"])

    def test_cover_position_unverified_is_omitted(self):
        result = generate({"project": "b" * 64, "widgets": [
            {"type": "cover", "name": "T1", "fields": {"command": "1/2/0", "stop": "1/2/1", "position": "1/2/2", "feedback": "1/2/10"}}]})
        self.assertIn('move_long_address: "1/2/0"', result["yaml"])
        self.assertIn('stop_address: "1/2/1"', result["yaml"])
        self.assertNotIn('1/2/2', result["yaml"])
        self.assertNotIn('position_state_address:', result["yaml"])
        self.assertIn("position_not_exported", [w["code"] for w in result["warnings"]])

    def test_missing_and_duplicate_commands_excluded(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "climate", "name": "Sala",
                  "fields": {"command": "2/1/1", "temperature": "2/1/0"}}]}
        result = generate(layout)
        self.assertEqual(result["counts"]["climate"], 0)
        self.assertIn("climate_missing_required", [w["code"] for w in result["warnings"]])
        layout["widgets"][0]["fields"].update({"target_temperature_state": "2/1/2",
            "heat_cool": "2/1/3", "heat_cool_state": "2/1/4", "operation_mode": "2/1/5"})
        result = generate(layout)
        self.assertEqual(result["counts"]["climate"], 1)
        for line in ('temperature_address: "2/1/0"', 'target_temperature_address: "2/1/1"',
                     'target_temperature_state_address: "2/1/2"', 'heat_cool_address: "2/1/3"',
                     'heat_cool_state_address: "2/1/4"', 'operation_mode_address: "2/1/5"'):
            self.assertIn(line, result["yaml"])
        self.assertFalse(result["applied"])

    def test_missing_and_duplicate_commands_still_excluded(self):
        result = generate({"project": "", "widgets": [
            {"type": "light", "name": "One", "fields": {"command": "1/1/0"}},
            {"type": "light", "name": "Two", "fields": {"command": "1/1/0"}},
            {"type": "light", "name": "Three", "fields": {"command": ""}}]})
        self.assertEqual(result["counts"]["light"], 1)
        self.assertIn("duplicate_command", [w["code"] for w in result["warnings"]])
        self.assertIn("missing_command", [w["code"] for w in result["warnings"]])

    def test_ets_evidence_confirms_dpt_without_guessing_missing(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "light", "name": "L1",
                  "fields": {"command": "1/1/0", "feedback": "1/1/4"}}]}
        evidence = validate_evidence({"project": "a" * 64, "addresses": [
            {"address": "1/1/0", "dpt": "DPST-1-1", "linked": True},
            {"address": "1/1/4", "dpt": "", "linked": True}]}, layout["project"])
        result = generate(layout, evidence)
        self.assertEqual(result["checks_confirmed"], 1)
        self.assertEqual(result["checks_pending"], 1)
        self.assertTrue(result["evidence_used"])

    def test_ets_unlinked_command_excluded(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "cover", "name": "T1",
                  "fields": {"command": "1/2/2", "stop": "1/2/1"}}]}
        result = generate(layout, {"1/2/2": {"dpt": "", "linked": False}})
        self.assertEqual(result["counts"]["cover"], 0)
        self.assertIn("command_unlinked", [w["code"] for w in result["warnings"]])

    def test_ets_unlinked_feedback_omitted(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "light", "name": "L1",
                  "fields": {"command": "1/1/0", "feedback": "1/1/4"}}]}
        result = generate(layout, {"1/1/0": {"dpt": "", "linked": True},
                                   "1/1/4": {"dpt": "", "linked": False}})
        self.assertNotIn('state_address:', result["yaml"])
        self.assertIn("field_unlinked", [w["code"] for w in result["warnings"]])

    def test_ets_project_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_evidence({"project": "b" * 64, "addresses": []}, "a" * 64)

    def test_ets_object_sizes_mark_compatible_not_verified(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "light", "name": "L1",
                  "fields": {"command": "1/1/0", "feedback": "1/1/4"}}]}
        evidence = validate_evidence({"project": "a" * 64, "addresses": [
            {"address": "1/1/0", "dpt": "", "linked": True,
             "connections": [{"size": "1 Bit", "function": "Commutazione"}]},
            {"address": "1/1/4", "dpt": "", "linked": True,
             "connections": [{"size": "1 Bit", "function": "Stato"}]}]}, layout["project"])
        result = generate(layout, evidence)
        self.assertEqual(result["checks_confirmed"], 0)
        self.assertEqual(result["checks_compatible"], 2)
        self.assertTrue(all(w.get("compatible") for w in result["warnings"]))

    def test_ets_object_size_mismatch_not_compatible(self):
        layout = {"project": "a" * 64, "widgets": [{"type": "light", "name": "L1",
                  "fields": {"command": "1/1/0"}}]}
        result = generate(layout, {"1/1/0": {"linked": True, "dpt": "",
                  "connections": [{"size": "1 Byte", "function": ""}]}})
        self.assertEqual(result["checks_compatible"], 0)
        self.assertTrue(any("INCOMPATIBILE" in w["message"] for w in result["warnings"]))

    def test_unknown_size_is_not_evidence(self):
        self.assertIsNone(object_bits("1 nibble"))
        self.assertEqual(object_bits("8 Bit"), 8)

    def test_oversized_evidence_connections_rejected(self):
        with self.assertRaisesRegex(ValueError, "object connections"):
            validate_evidence({"project": "a" * 64, "addresses": [
                {"address": "1/1/0", "linked": True, "dpt": "",
                 "connections": [{"size": "1 Bit", "function": ""}] * 13}]}, "a" * 64)


if __name__ == "__main__":
    unittest.main()
