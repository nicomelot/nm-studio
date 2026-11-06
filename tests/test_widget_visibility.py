import copy
import unittest
from nm_bridge.widget_layout import validate
from nm_bridge.lovelace_generator import generate
from nm_bridge.missing_ha_generator import preview


class WidgetVisibilityTests(unittest.TestCase):
    def layout(self):
        return {'version': 1, 'project': 'a'*64, 'widgets': [
            {'type': 'light', 'name': 'Lampada', 'room': 'Sala', 'visible': False,
             'entity_id': 'light.lampada', 'fields': {'command': '1/1/1'}}]}

    def test_hidden_function_remains_persisted_but_not_on_dashboard(self):
        layout = validate(self.layout())
        before = copy.deepcopy(layout)
        self.assertIs(layout['widgets'][0]['visible'], False)
        result = generate(layout, [{'entity_id': 'light.lampada'}])
        self.assertEqual(result['summary']['tiles'], 0)
        self.assertEqual(result['summary']['placeholders'], 0)
        self.assertEqual(layout, before)
        self.assertEqual(layout['widgets'][0]['entity_id'], 'light.lampada')

    def test_visibility_does_not_change_installation_eligibility(self):
        layout = self.layout()
        layout['widgets'][0]['entity_id'] = ''
        result = preview(validate(layout), [])
        self.assertEqual(len(result['devices']), 1)
        self.assertEqual(result['devices'][0]['fields']['command'], '1/1/1')

    def test_legacy_visibility_defaults_visible_and_rejects_non_boolean(self):
        layout = self.layout()
        del layout['widgets'][0]['visible']
        result = generate(validate(layout), [{'entity_id': 'light.lampada'}])
        self.assertEqual(result['summary']['tiles'], 1)
        layout['widgets'][0]['visible'] = 'false'
        with self.assertRaises(ValueError):
            validate(layout)
