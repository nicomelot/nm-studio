import unittest

from nm_bridge.knx_panel_apply import create_one, KNXApplyError
from nm_bridge.knx_entity_plan import build


class FakePanel:
    def __init__(self, used=None, validation=None):
        self.used = {} if used is None else used
        self.validation = validation or {"success": True}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def call(self, command, **kwargs):
        self.calls.append(command)
        if command == "knx/get_base_data":
            return {"supported_platforms": ["light", "cover"]}
        if command == "knx/get_entities_by_group":
            return self.used
        if command == "knx/validate_entity":
            return self.validation
        if command == "knx/create_entity":
            return {"success": True, "entity_id": "light.created"}
        raise AssertionError(command)


class PanelApplyTests(unittest.TestCase):
    def setUp(self):
        self.layout = {"version": 1, "project": "a" * 64, "rooms": [], "structure": [], "widgets": [
            {"name": "L1", "room": "Ufficio", "type": "light", "fields": {"command": "1/1/0", "feedback": "1/1/4"}}]}
        # The review generator requires a layout-specific source fingerprint.
        from nm_bridge.missing_ha_generator import preview
        evidence = preview(self.layout, [])
        self.request = {"source_fingerprint": evidence["source_fingerprint"], "devices": [
            {"index": 0, "approved": True, "name": "L1", "fields": {"command": "1/1/0", "feedback": "1/1/4"}}]}
        plan = build(self.layout, self.request)
        self.payload = {"confirm": True, "backup_confirmed": True, "ets_confirmed": True,
                        "review": self.request, "source_fingerprint": plan["source_fingerprint"],
                        "call_index": 0, "expected_call": plan["calls"][0]}

    def test_creates_only_after_validation(self):
        fake = FakePanel()
        result = create_one(self.layout, self.payload, connection_factory=lambda: fake)
        self.assertEqual(result["entity_id"], "light.created")
        self.assertEqual(fake.calls[-2:], ["knx/validate_entity", "knx/create_entity"])

    def test_refuses_without_backup_and_confirmation(self):
        fake = FakePanel()
        for key in ("confirm", "backup_confirmed", "ets_confirmed"):
            with self.subTest(key=key), self.assertRaises(KNXApplyError):
                create_one(self.layout, {**self.payload, key: False}, connection_factory=lambda: fake)
        self.assertEqual(fake.calls, [])

    def test_refuses_duplicate_ga(self):
        fake = FakePanel(used={"1/1/0": ["light.existing"]})
        with self.assertRaisesRegex(KNXApplyError, "GA già presente"):
            create_one(self.layout, self.payload, connection_factory=lambda: fake)
        self.assertNotIn("knx/create_entity", fake.calls)

    def test_refuses_modified_call(self):
        fake = FakePanel()
        with self.assertRaisesRegex(KNXApplyError, "cambiata"):
            create_one(self.layout, {**self.payload, "expected_call": {"type": "knx/create_entity"}}, connection_factory=lambda: fake)
        self.assertEqual(fake.calls, [])

    def test_refuses_invalid_knx_schema(self):
        fake = FakePanel(validation={"success": False, "errors": ["invalid"]})
        with self.assertRaisesRegex(KNXApplyError, "Validazione KNX"):
            create_one(self.layout, self.payload, connection_factory=lambda: fake)
        self.assertNotIn("knx/create_entity", fake.calls)


    def test_plan_rejects_missing_dimmer_level_or_cover_stop(self):
        from nm_bridge.missing_ha_generator import fingerprint
        for kind in ('dimmer', 'cover', 'climate'):
            layout = {**self.layout, 'widgets': [{**self.layout['widgets'][0], 'type': kind, 'fields': {'command': '1/1/0'}}]}
            request = {'source_fingerprint': fingerprint(layout), 'devices': [{'index': 0, 'approved': True, 'name': 'Test', 'fields': {'command': '1/1/0'}}]}
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build(layout, request)

    def test_dimmer_feedback_and_cover_position_mapping(self):
        from nm_bridge.missing_ha_generator import fingerprint
        for kind, fields in [('dimmer', {'command': '1/1/0', 'feedback': '1/1/1', 'brightness': '1/1/2', 'brightness_feedback': '1/1/3'}),
                             ('cover', {'command': '1/2/0', 'stop': '1/2/1', 'position': '1/2/2'})]:
            layout = {**self.layout, 'widgets': [{**self.layout['widgets'][0], 'type': kind, 'fields': fields}]}
            request = {'source_fingerprint': fingerprint(layout), 'devices': [{'index': 0, 'approved': True, 'name': 'Test', 'fields': fields}]}
            data = build(layout, request)['calls'][0]['data']
            if kind == 'dimmer':
                self.assertEqual(data['brightness_state_address'], '1/1/3')
                self.assertEqual(data['state_address'], '1/1/1')
            else:
                self.assertEqual(data['stop_address'], '1/2/1')
                self.assertNotIn('position_address', data)


if __name__ == "__main__":
    unittest.main()

