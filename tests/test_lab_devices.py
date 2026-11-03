import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nm_bridge.lab_devices import build, candidates, building_location
from nm_bridge.lab_virtual import inspect, install, replace
from nm_bridge.lab_dashboard import preview, publish
from test_dashboard_publisher import FakeClient
from test_ets_import import archive_with_addresses
from nm_bridge.ets_import import preview as ets_preview


def project(kinds=("light", "dimmer", "cover", "scene", "sensor", "binary_sensor")):
    return {"mode": "virtual_devices", "project": "a" * 64, "devices": [
        {"kind": kind, "command": f"1/0/{i}", "name": kind, "room": "Magazzino"}
        for i, kind in enumerate(kinds)]}


def inventory(payload):
    result = []
    for item in build(payload)["manifest"]:
        result.append({"entity_id": item["entity_id"], "state": "unknown" if item["kind"] == "scene" else "off"})
        result.extend({"entity_id": control, "state": "0"} for control in item["controls"])
    return result


class LabDevicesTests(unittest.TestCase):
    def test_building_common_floor_and_ambiguous_locations(self):
        data = {'devices': [{'id': 'd1', 'ets_id': 'ets1'}, {'id': 'd2', 'ets_id': 'ets2'}],
                'building': [{'path': 'FR / MAGAZZINO PRIMO / PULSANTIERA', 'devices': ['ets1']},
                             {'path': 'FR / MAGAZZINO PRIMO / SCATOLA DI DERIVAZIONE', 'devices': ['ets2']}],
                'addresses': [{'address': '1/1/0', 'connections': [{'device_id': 'd1'}, {'device_id': 'd2'}]}],
                'suggestions': [{'command': '1/1/0', 'name': 'L1', 'kind': 'light', 'room': 'Da assegnare'}]}
        self.assertEqual(building_location(data, '1/1/0'), 'FR / MAGAZZINO PRIMO')
        self.assertEqual(candidates(data)[0]['room'], 'FR / MAGAZZINO PRIMO')
        self.assertIn('room_source', candidates(data)[0])
        data['building'][1]['path'] = 'FR / MAGAZZINO TERRA / QUADRO'
        self.assertIsNone(building_location(data, '1/1/0'))
        data['building'] = []
        self.assertIsNone(building_location(data, '1/1/0'))

    def test_lab_uses_unambiguous_room_proposals(self):
        data = {'suggestions': [{'kind': 'light', 'command': '1/1/0', 'name': 'L1', 'room': 'Da assegnare'}],
                'room_matches': [{'command': '1/1/0', 'room': 'Edificio / Ufficio', 'confidence': 'ets_function'}]}
        self.assertEqual(candidates(data)[0]['room'], 'Edificio / Ufficio')
        data['room_matches'][0]['confidence'] = 'ambiguous'
        self.assertEqual(candidates(data)[0]['room'], 'Da assegnare')
        self.assertEqual(data['suggestions'][0]['room'], 'Da assegnare')

    def test_ets_without_thermostats_reaches_installable_package(self):
        imported = ets_preview(archive_with_addresses([
            (2048, "ON/OFF L1"), (2049, "STATO LED L1"),
            (2560, "Movimento su/giu T1"), (2561, "Arresto T1"), (2562, "Posizione T1")], linked=range(5)))
        proposed = candidates(imported)
        self.assertTrue(proposed)
        self.assertNotIn("climate", {d["kind"] for d in proposed})
        request = {"mode": "virtual_devices", "project": imported["project_key"], "devices": proposed}
        self.assertGreater(build(request)["devices"], 0)
        self.assertNotIn("climate", json.loads(build(request)["yaml"]))

    def test_all_supported_devices_and_deterministic_project_isolation(self):
        request = project(("light", "dimmer", "cover", "scene", "sensor", "binary_sensor", "climate"))
        plan = build(request)
        self.assertEqual(plan["devices"], 7)
        self.assertEqual(plan["zones"], 1)
        self.assertEqual(build({**request, "devices": request["devices"][::-1]})["sha256"], plan["sha256"])
        other = build({**request, "project": "b" * 64})
        self.assertFalse({d["entity_id"] for d in plan["manifest"]} & {d["entity_id"] for d in other["manifest"]})

    def test_package_actions_only_target_generated_helpers(self):
        package = json.loads(build(project())["yaml"])
        helpers = {f"{domain}.{key}" for domain in ("input_boolean", "input_number", "input_button") for key in package.get(domain, {})}
        actions = []
        def walk(value):
            if isinstance(value, dict):
                if "action" in value:
                    actions.append(value)
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(package)
        self.assertGreater(len(actions), 5)
        for action in actions:
            self.assertIn(action["target"]["entity_id"], helpers)
            self.assertIn(action["action"], {"input_boolean.turn_on", "input_boolean.turn_off", "input_number.set_value"})
        self.assertNotIn("knx", package)
        dimmer = package["template"][0]["light"][1]
        self.assertEqual(dimmer["set_level"][-1]["action"], "input_boolean.turn_on")

    def test_invalid_payload_and_template_injection_are_rejected(self):
        for request in (None, {}, {**project(), "project": "../real"}, {**project(), "devices": []},
                        {**project(), "devices": project()["devices"] * 2}):
            with self.subTest(request=request), self.assertRaises(ValueError): build(request)
        for changes in ({"name": "{{ states('sensor.secret') }}"}, {"command": "32/0/0"},
                        {"kind": "knx"}, {"room": "a\nknx:"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build({**project(), "devices": [{**project()["devices"][0], **changes}]})

    def test_install_is_exact_idempotent_and_never_overwrites_real_files(self):
        request = project()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / "configuration.yaml"
            config.write_text("homeassistant:\n  packages: !include_dir_named packages\n")
            (root / "packages").mkdir()
            real = root / "packages" / "real_knx.yaml"
            real.write_text("knx: {}")
            before = config.read_bytes()
            plan = inspect(request, root)
            data = {**request, "confirm": True, "expected_sha256": plan["sha256"]}
            self.assertTrue(install(data, root)["installed"])
            self.assertTrue(install(data, root)["unchanged"])
            self.assertEqual((root / "packages" / "nm_lab_virtual.yaml").read_bytes(), build(request)["yaml"].encode())
            self.assertEqual(real.read_text(), "knx: {}")
            self.assertEqual(config.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, "Anteprima"):
                install({**data, "devices": data["devices"][:1]}, root)
            changed = {**request, "project": "b" * 64}
            with self.assertRaisesRegex(ValueError, "sovrascrittura"):
                install({**changed, "confirm": True, "expected_sha256": build(changed)["sha256"]}, root)

    def test_symlink_rejection_without_platform_privileges(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaises(ValueError): inspect(project(), folder)

    def test_switching_projects_requires_fresh_review_and_exact_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "configuration.yaml").write_text("homeassistant:\n  packages: !include_dir_named packages\n")
            first = project()
            install({**first, "confirm": True, "expected_sha256": build(first)["sha256"]}, root)
            target = root / "packages" / "nm_lab_virtual.yaml"
            before = target.read_bytes()
            second = {**first, "project": "b" * 64}
            plan = inspect(second, root)
            self.assertTrue(plan["replaceable"])
            request = {**second, "confirm": True, "replace_confirmed": True,
                       "expected_sha256": plan["sha256"], "expected_existing_sha256": plan["existing_sha256"]}
            with self.assertRaisesRegex(ValueError, "Conferma"):
                replace({**request, "replace_confirmed": False}, root, root / "backup")
            target.write_bytes(before + b"\n")
            with self.assertRaisesRegex(ValueError, "anteprima"):
                replace(request, root, root / "backup")
            self.assertFalse((root / "backup").exists())
            target.write_bytes(before)
            self.assertTrue(replace(request, root, root / "backup")["backup_created"])
            self.assertEqual(next((root / "backup").glob("*.yaml")).read_bytes(), before)
            self.assertEqual(target.read_bytes(), build(second)["yaml"].encode())
            target.write_text("knx: {}")
            plan = inspect(first, root)
            self.assertFalse(plan["replaceable"])
            with self.assertRaisesRegex(ValueError, "riconosciuto"):
                replace({**first, "confirm": True, "replace_confirmed": True, "expected_sha256": plan["sha256"],
                         "expected_existing_sha256": plan["existing_sha256"]}, root, root / "backup")

    def test_scenes_and_sensors_are_proposed_without_guessing_unknown_dpts(self):
        data = {"suggestions": [], "addresses": [
            {"address": "1/4/0", "name": "Scena", "dpt": "DPST-17-1", "linked": True},
            {"address": "1/5/0", "name": "Temperatura", "dpt": "DPST-9-1", "linked": True},
            {"address": "1/3/0", "name": "Presenza", "dpt": "DPST-1-18", "linked": True},
            {"address": "1/5/1", "name": "Sensore", "dpt": "", "linked": True}]}
        self.assertEqual([d["kind"] for d in candidates(data)], ["scene", "sensor", "binary_sensor"])

    def test_dashboard_checks_inventory_and_only_publishes_virtual_entities(self):
        request = project()
        empty = preview(request, [{"entity_id": "light.real", "state": "on"}])
        self.assertEqual(empty["summary"]["tiles"], 0)
        with self.assertRaisesRegex(ValueError, "mancanti"):
            publish({**request, "confirm": True}, [], client_factory=lambda: self.fail("Must not connect"))
        live = inventory(request)
        plan = preview(request, live)
        self.assertEqual(plan["summary"]["tiles"], 6)
        self.assertEqual(plan["warnings"], [])
        fake = FakeClient()
        result = publish({**request, "confirm": True, "expected_fingerprint": plan["fingerprint"]}, live, lambda: fake)
        self.assertTrue(result["created"])
        self.assertTrue(all(method.startswith("lovelace/") for method, _ in fake.calls))
        self.assertEqual(fake.saved["title"], "NM Control LAB")
        self.assertNotIn("light.real", json.dumps(fake.saved))

    def test_dashboard_stale_preview_and_existing_dashboard_are_blocked(self):
        request = project()
        live = inventory(request)
        plan = preview(request, live)
        with self.assertRaisesRegex(ValueError, "Anteprima"):
            publish({**request, "confirm": True, "expected_fingerprint": "bad"}, live)
        fake = FakeClient(existing=[plan["url_path"]])
        with self.assertRaisesRegex(ValueError, "esistente"):
            publish({**request, "confirm": True, "expected_fingerprint": plan["fingerprint"]}, live, lambda: fake)
        self.assertEqual(len(fake.calls), 1)
