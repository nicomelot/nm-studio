import tempfile
import unittest
from pathlib import Path

from nm_bridge.lab_virtual import build, inspect, install


def payload():
    return {"mode": "virtual_climate", "zones": [
        {"kind": "climate", "command": "2/0/2", "temperature": "2/0/0"},
        {"kind": "climate", "command": "2/1/2", "temperature": "2/1/0"}]}


class VirtualLabTests(unittest.TestCase):
    def test_preview_has_only_virtual_heaters_and_valid_ha_ids(self):
        plan = build(payload())
        self.assertEqual(plan["zones"], 2)
        self.assertEqual(plan["yaml"].count("platform: generic_thermostat"), 2)
        self.assertIn("heater: input_boolean.nm_lab_2_0_2_heater", plan["yaml"])
        self.assertIn("target_sensor: sensor.nm_lab_2_0_2_temperatura", plan["yaml"])
        self.assertFalse(plan["knx_traffic"])

    def test_install_requires_preexisting_package_include_and_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = build(payload())
            request = {**payload(), "confirm": True, "expected_sha256": plan["sha256"]}
            self.assertFalse(inspect(payload(), root)["ready"])
            with self.assertRaisesRegex(ValueError, "Abilita"):
                install(request, root)
            (root / "configuration.yaml").write_text("homeassistant:\n  packages: !include_dir_named packages\n")
            with self.assertRaisesRegex(ValueError, "Conferma"):
                install({**request, "confirm": False}, root)
            installed = install(request, root)
            self.assertTrue(installed["installed"])
            target = root / "packages" / "nm_lab_virtual.yaml"
            self.assertEqual(target.read_text(), plan["yaml"])
            self.assertTrue(install(request, root)["unchanged"])
            with self.assertRaisesRegex(ValueError, "sovrascrittura"):
                install({**request, "zones": [payload()["zones"][0]],
                         "expected_sha256": build({**payload(), "zones": [payload()["zones"][0]]})["sha256"]}, root)

    def test_rejects_unsafe_zones_and_symlinked_target(self):
        with self.assertRaises(ValueError):
            build({**payload(), "zones": [payload()["zones"][0]] * 2})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "configuration.yaml").write_text("homeassistant:\n  packages: !include_dir_named packages\n")
            (root / "packages").mkdir()
            (root / "packages" / "nm_lab_virtual.yaml").symlink_to(root / "configuration.yaml")
            with self.assertRaisesRegex(ValueError, "sicuro"):
                inspect(payload(), root)


if __name__ == "__main__":
    unittest.main()
