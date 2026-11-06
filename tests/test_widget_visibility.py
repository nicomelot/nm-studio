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

    def test_off_button_mode_roundtrip_and_invalid_feedback(self):
        layout = self.layout()
        layout['widgets'][0]['command_mode'] = 'off_only'
        checked = validate(layout)
        self.assertEqual(validate(checked), checked)
        self.assertEqual(checked['widgets'][0]['command_mode'], 'off_only')
        layout['widgets'][0]['fields']['feedback'] = '1/1/1'
        with self.assertRaises(ValueError): validate(layout)
        layout['widgets'][0]['fields'].pop('feedback')
        for mode in ('invalid', None, True):
            layout['widgets'][0]['command_mode'] = mode
            with self.assertRaises(ValueError): validate(layout)

    def test_off_button_has_only_explicit_off_action_no_state_or_toggle(self):
        layout = self.layout()
        layout['widgets'][0].update(visible=True, command_mode='off_only')
        result = generate(validate(layout), [{'entity_id': 'light.lampada'}])
        cards = [c for v in result['dashboard']['views'] for s in v['sections'] for c in s['cards']]
        controls = [c for c in cards if c.get('name') == 'Lampada']
        self.assertTrue(controls)
        for card in controls:
            self.assertEqual(card['type'], 'button')
            self.assertNotIn('entity', card)
            self.assertFalse(card['show_state'])
            self.assertEqual(card['tap_action']['perform_action'], 'light.turn_off')
            self.assertEqual(card['hold_action'], {'action': 'none'})
        self.assertFalse(any(c['type'] == 'entity-filter' for c in cards))
