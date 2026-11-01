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
