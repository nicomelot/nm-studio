import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nm_bridge import module_plan


class ModulePlanTests(unittest.TestCase):
    def test_roundtrip_and_no_auto_approval(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(module_plan, "PATH", Path(folder) / "modules.json"):
            plan = module_plan.empty_plan()
            plan["modules"]["knx"] = {"enabled": True, "checked": [1, 0], "notes": "  Verificare GA  "}
            saved = module_plan.save(plan)
            self.assertEqual(saved["modules"]["knx"]["checked"], [0, 1])
            self.assertEqual(module_plan.read(), saved)
            self.assertEqual(saved["modules"]["knx"]["notes"], "Verificare GA")
            self.assertFalse(saved["modules"]["solar"]["enabled"])

    def test_bad_checklist_is_rejected(self):
        plan = module_plan.empty_plan()
        plan["modules"]["solar"]["checked"] = [99]
        with self.assertRaises(ValueError):
            module_plan.validate(plan)

    def test_unknown_module_is_rejected(self):
        plan = module_plan.empty_plan()
        plan["modules"]["unknown"] = {"enabled": True, "checked": [], "notes": ""}
        with self.assertRaises(ValueError):
            module_plan.validate(plan)

    def test_candidates_require_matching_domain_name_and_unit(self):
        entities = [
            {"entity_id": "sensor.pv_power", "name": "Produzione FV", "unit": "W", "state": "3500"},
            {"entity_id": "sensor.grid", "name": "Scambio rete", "unit": "W", "state": "500"},
            {"entity_id": "sensor.battery_soc", "name": "Batteria SOC", "unit": "%", "state": "65"},
            {"entity_id": "sensor.pv_energy", "name": "Produzione FV", "unit": "kWh", "state": "22"},
            {"entity_id": "climate.office", "name": "Riscaldamento ufficio", "state": "heat"},
        ]
        result = module_plan.suggest_entities(entities)
        self.assertFalse(result["automatic_approval"])
        self.assertEqual([x["entity_id"] for x in result["suggestions"]["solar"]["pv_power"]], ["sensor.pv_power"])
        self.assertEqual(result["suggestions"]["climate"]["climate_mode"][0]["entity_id"], "climate.office")

    def test_assignment_requires_known_role_and_entity_id(self):
        plan = module_plan.empty_plan()
        plan["modules"]["solar"]["assignments"] = {"pv_power": "sensor.pv_power"}
        self.assertEqual(module_plan.validate(plan)["modules"]["solar"]["assignments"], {"pv_power": "sensor.pv_power"})
        plan["modules"]["solar"]["assignments"] = {"pv_power": "../../secrets"}
        with self.assertRaises(ValueError):
            module_plan.validate(plan)
