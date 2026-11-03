import tempfile
import unittest
from pathlib import Path

from nm_bridge.lab_virtual import build, inspect, install, packages_setup_preview, enable_packages


def payload():
    return {"mode": "virtual_climate", "zones": [
        {"kind": "climate", "command": "2/0/2", "temperature": "2/0/0"},
        {"kind": "climate", "command": "2/1/2", "temperature": "2/1/0"}]}


class VirtualLabTests(unittest.TestCase):
    def test_packages_under_other_mapping_never_enable_lab(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "configuration.yaml").write_text("homeassistant:\n  name: Test\nother:\n  packages: !include_dir_named packages\n")
            self.assertFalse(inspect(payload(), root)["ready"])
            with self.assertRaises(ValueError): packages_setup_preview(root)

    def test_no_final_newline_and_nonstandard_indentation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "configuration.yaml"
            config.write_text("homeassistant:")
            plan = packages_setup_preview(root)
            enable_packages({"confirm": True, "expected_sha256": plan["expected_sha256"]}, root, root / "backup")
            self.assertTrue(inspect(payload(), root)["ready"])
            config.write_text("homeassistant:\n    name: Test\n")
            with self.assertRaisesRegex(ValueError, "Indentazione"): packages_setup_preview(root)

    def test_packages_activation_is_confirmed_backed_up_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "configuration.yaml"
            config.write_text("default_config:\n\nfrontend:\n")
            check = packages_setup_preview(root)
            self.assertTrue(check["ready"])
            self.assertFalse(check["already_enabled"])
            backup = root / "safekeeping"
            with self.assertRaisesRegex(ValueError, "Conferma"):
                enable_packages({"confirm": False, "expected_sha256": check["expected_sha256"]}, root, backup)
            result = enable_packages({"confirm": True, "expected_sha256": check["expected_sha256"]}, root, backup)
            self.assertTrue(result["backup_created"])
            self.assertIn("homeassistant:\n  packages: !include_dir_named packages", config.read_text())
            self.assertEqual(len(list(backup.glob("configuration-*.yaml"))), 1)
            self.assertTrue(packages_setup_preview(root)["already_enabled"])
            self.assertTrue((root / "packages").is_dir())

    def test_packages_activation_preserves_existing_homeassistant_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "configuration.yaml"
            config.write_text("homeassistant:\n  name: NM Test\n\nlogger:\n  default: warning\n")
            check = packages_setup_preview(root)
            enable_packages({"confirm": True, "expected_sha256": check["expected_sha256"]}, root, root / "backups")
            self.assertIn("homeassistant:\n  packages: !include_dir_named packages\n  name: NM Test", config.read_text())
            self.assertIn("logger:\n  default: warning", config.read_text())

    def test_packages_activation_refuses_custom_includes_and_stale_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "configuration.yaml"
            config.write_text("homeassistant:\n  packages: !include_dir_merge_named custom\n")
            with self.assertRaisesRegex(ValueError, "packages"):
                packages_setup_preview(root)
            config.write_text("default_config:\n")
            check = packages_setup_preview(root)
            config.write_text("default_config:\n# changed\n")
            with self.assertRaisesRegex(ValueError, "modificato"):
                enable_packages({"confirm": True, "expected_sha256": check["expected_sha256"]}, root, root / "backups")
            self.assertFalse((root / "backups").exists())

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
            try:
                (root / "packages" / "nm_lab_virtual.yaml").symlink_to(root / "configuration.yaml")
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    self.skipTest("Windows host does not grant symlink creation; exercised on Linux CI")
                raise
            with self.assertRaisesRegex(ValueError, "sicuro"):
                inspect(payload(), root)


if __name__ == "__main__":
    unittest.main()

