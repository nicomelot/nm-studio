import copy
import unittest
from unittest.mock import patch
from nm_bridge import installation_review as module
from nm_bridge.missing_ha_generator import fingerprint


class Fake:
    def __init__(self):
        self.config = {'platform': 'light', 'data': {'entity': {'name': 'Nome cliente'},
                       'knx': {'ga_switch': {'write': '1/1/1'}, 'transition': 2}}}
        self.calls = []
        self.used = {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def call(self, method, **args):
        self.calls.append((method, args))
        if method == 'knx/get_entity_config': return copy.deepcopy(self.config)
        if method == 'knx/get_entities_by_group': return self.used
        if method == 'knx/get_base_data': return {'supported_platforms': ['light', 'cover']}
        if method == 'knx/validate_entity': return {'success': True}
        if method == 'knx/update_entity':
            self.config['data'] = copy.deepcopy(args['data'])
            return {'success': True, 'entity_id': None}
        raise AssertionError(method)


class InstallationReviewTests(unittest.TestCase):
    def setUp(self):
        self.ws = Fake()
        self.layout = {'version': 1, 'project': 'a'*64, 'widgets': [
            {'name': 'Importato', 'type': 'dimmer', 'room': 'Sala', 'entity_id': 'light.sala',
             'fields': {'command': '1/1/1', 'brightness': '1/1/2', 'brightness_feedback': '1/1/3'}}]}
    def payload(self):
        return {'confirm': True, 'ets_confirmed': True, 'backup_confirmed': True,
                'source_fingerprint': fingerprint(self.layout), 'index': 0,
                'expected': module.compare(self.layout, 0, self.ws)}
    def test_additive_update_keeps_id_name_and_options_and_reads_back(self):
        payload = self.payload()
        self.assertEqual(payload['expected']['status'], 'update')
        with patch.object(module, 'read_layout', return_value=self.layout):
            result = module.apply_one(payload, lambda: self.ws)
        self.assertEqual(result['entity_id'], 'light.sala')
        self.assertEqual(self.ws.config['data']['entity']['name'], 'Nome cliente')
        self.assertEqual(self.ws.config['data']['knx']['transition'], 2)
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'present')
        self.assertFalse(any(m == 'knx/create_entity' for m, _ in self.ws.calls))
    def test_changed_config_or_missing_consent_never_updates(self):
        payload = self.payload()
        self.ws.config['data']['entity']['name'] = 'Modificato in HA'
        with patch.object(module, 'read_layout', return_value=self.layout):
            with self.assertRaises(ValueError): module.apply_one(payload, lambda: self.ws)
            with self.assertRaises(ValueError): module.apply_one({**payload, 'confirm': False}, lambda: self.ws)
        self.assertFalse(any(m == 'knx/update_entity' for m, _ in self.ws.calls))
    def test_conflict_duplicate_and_wrong_association_are_review_only(self):
        self.ws.config['data']['knx']['ga_brightness'] = {'write': '2/1/1'}
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'review')
        del self.ws.config['data']['knx']['ga_brightness']
        self.ws.used = {'1/1/2': [{'unique_id': 'other'}]}
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'review')
        self.ws.used = {}
        self.ws.config['data']['knx']['ga_switch']['write'] = '2/1/0'
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'review')
    def test_preview_is_read_only_and_covers_all_states(self):
        self.layout['widgets'].append({'name': 'Nuova', 'type': 'light', 'room': 'Bagno', 'fields': {'command': '2/0/0'}})
        self.layout['widgets'].append({'name': 'Incompleta', 'type': 'cover', 'fields': {'command': '2/0/1'}})
        result = module.preview(self.layout, lambda: self.ws)
        self.assertEqual([d['status'] for d in result['devices']], ['update', 'create', 'review'])
        self.assertTrue(all(m.startswith('knx/get_') for m, _ in self.ws.calls))

    def test_existing_ga_and_duplicate_commands_cannot_be_created_again(self):
        self.layout['widgets'][0]['entity_id'] = ''
        self.ws.used = {'1/1/1': [{'unique_id': 'existing'}]}
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'review')
        self.ws.used = {}
        self.layout['widgets'].append(copy.deepcopy(self.layout['widgets'][0]))
        self.assertEqual(module.compare(self.layout, 0, self.ws)['status'], 'review')

    def test_stale_layout_rejected_before_contacting_ha(self):
        payload = self.payload()
        self.layout['widgets'][0]['name'] = 'Changed'
        self.ws.calls.clear()
        with patch.object(module, 'read_layout', return_value=self.layout):
            with self.assertRaises(ValueError): module.apply_one(payload, lambda: self.ws)
        self.assertEqual(self.ws.calls, [])

    def test_creation_uses_persistent_install_step_and_current_plan(self):
        self.layout['widgets'][0]['entity_id'] = ''
        payload = self.payload()
        with patch.object(module, 'read_layout', return_value=self.layout), patch.object(module, 'install_step', return_value={'linked': True}) as install:
            module.apply_one(payload, lambda: self.ws)
        args = install.call_args.args[0]
        self.assertEqual(args['expected_call']['platform'], 'light')
        self.assertEqual(args['review']['devices'][0]['index'], 0)
        self.assertEqual(args['expected_call']['data']['knx']['ga_brightness']['write'], '1/1/2')
