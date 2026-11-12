import copy
import unittest
from unittest.mock import patch
from nm_bridge import commissioning as module
from nm_bridge.missing_ha_generator import fingerprint
from test_installation_review import Fake


class TestHA(Fake):
    def __init__(self):
        super().__init__()
        self.config['data']['knx']['ga_brightness'] = {'write': '1/1/2'}
        self.states = [{'entity_id': 'light.sala', 'state': 'on', 'attributes': {'supported_color_modes': ['brightness']}}]
    def call(self, method, **args):
        if method in ('get_states', 'call_service'):
            self.calls.append((method, args))
            return copy.deepcopy(self.states) if method == 'get_states' else {'context': {}}
        return super().call(method, **args)


class CommissioningTests(unittest.TestCase):
    def setUp(self):
        self.ws = TestHA()
        self.layout = {'version': 1, 'project': 'a'*64, 'widgets': [
            {'type': 'dimmer', 'name': 'Sala', 'entity_id': 'light.sala',
             'fields': {'command': '1/1/1', 'brightness': '1/1/2'}}]}
    def payload(self, **kwargs):
        return dict(confirm=True, index=0, entity_id='light.sala', action='brightness', value=35,
                    source_fingerprint=fingerprint(self.layout), **kwargs)
    def execute(self, payload):
        with patch.object(module, 'read_layout', return_value=self.layout):
            return module.command(payload, lambda: self.ws)
    def writes(self):
        return [a for m, a in self.ws.calls if m == 'call_service']
    def test_only_one_explicit_service_call_with_exact_target(self):
        self.assertTrue(self.execute(self.payload())['sent'])
        self.assertEqual(self.writes(), [{'domain': 'light', 'service': 'turn_on',
                         'target': {'entity_id': 'light.sala'}, 'service_data': {'brightness_pct': 35}}])
    def test_missing_consent_stale_target_invalid_action_and_percent_never_send(self):
        for changes in ({'confirm': False}, {'entity_id': 'light.other'}, {'source_fingerprint': 'old'},
                        {'action': 'toggle'}, {'value': 101}, {'value': True}, {'value': '50'}, {'index': -1}):
            with self.assertRaises(ValueError): self.execute({**self.payload(), **changes})
        self.assertEqual(self.writes(), [])
    def test_unavailable_or_unaligned_entities_never_send(self):
        self.ws.states[0]['state'] = 'unavailable'
        with self.assertRaises(ValueError): self.execute(self.payload())
        self.ws.states[0]['state'] = 'on'
        self.ws.config['data']['knx']['ga_switch']['write'] = '2/1/0'
        with self.assertRaises(ValueError): self.execute(self.payload())
        self.assertEqual(self.writes(), [])
    def test_onoff_entity_cannot_be_dimmed(self):
        self.ws.states[0]['attributes']['supported_color_modes'] = ['onoff']
        with self.assertRaises(ValueError): self.execute(self.payload())
        self.assertEqual(self.writes(), [])

    def test_native_button_press_checks_the_saved_payload(self):
        entity = 'button.campanello'
        self.layout['widgets'][0].update(type='button', entity_id=entity, command_mode='on_only',
                                         fields={'command': '1/1/1'})
        knx = {'ga_send': {'write': '1/1/1'}, 'data': {'payload': '0x1', 'payload_length': 0}}
        self.ws.config = {'platform': 'button', 'data': {'entity': {'name': 'Campanello'}, 'knx': knx}}
        self.ws.states = [{'entity_id': entity, 'state': 'unknown'}]
        payload = {**self.payload(), 'entity_id': entity, 'action': 'press'}
        self.execute(payload)
        self.assertEqual(self.writes(), [{'domain': 'button', 'service': 'press',
                                         'target': {'entity_id': entity}, 'service_data': {}}])
        knx['data']['payload'] = '0x0'
        with self.assertRaises(ValueError):
            self.execute(payload)
        with self.assertRaises(ValueError):
            self.execute({**payload, 'action': 'off'})
        self.assertEqual(len(self.writes()), 1)
    def test_cover_stop_is_allowed_even_when_state_unavailable(self):
        self.layout['widgets'][0].update(type='cover', entity_id='cover.sala', fields={'command': '1/1/1', 'stop': '1/1/2'})
        self.ws.config = {'platform': 'cover', 'data': {'entity': {'name': 'Sala'}, 'knx': {'ga_up_down': {'write': '1/1/1'}, 'ga_stop': {'write': '1/1/2'}}}}
        self.ws.states = [{'entity_id': 'cover.sala', 'state': 'unavailable', 'attributes': {'supported_features': 11}}]
        payload = {**self.payload(), 'entity_id': 'cover.sala', 'action': 'stop'}
        self.execute(payload)
        self.assertEqual(self.writes()[0]['service'], 'stop_cover')
        with self.assertRaises(ValueError): self.execute({**payload, 'action': 'open'})
        self.assertEqual(len(self.writes()), 1)

    def test_http_route_requires_ingress_and_consent(self):
        from test_lab_http import request, bridge
        with patch.object(bridge, 'commissioning_command', wraps=module.command) as handler:
            self.assertEqual(request('/knx/commission-command', {}, address='192.168.1.20')['status'], 403)
            handler.assert_not_called()
            self.assertEqual(request('/knx/commission-command', {})['status'], 400)

    def test_off_button_repeated_presses_never_turn_on_even_without_state(self):
        self.layout['widgets'][0].update(type='light', command_mode='off_only', fields={'command': '1/1/1'})
        self.ws.states[0]['state'] = 'unknown'
        for action in ('on', 'toggle', 'brightness'):
            with self.assertRaisesRegex(ValueError, 'solo lo spegnimento'):
                self.execute({**self.payload(), 'action': action})
        self.assertEqual(self.writes(), [])
        for _ in range(2):
            self.execute({**self.payload(), 'action': 'off'})
        self.assertEqual([c['service'] for c in self.writes()], ['turn_off', 'turn_off'])
