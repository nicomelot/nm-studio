import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nm_bridge import widget_layout
from nm_bridge.knx_install import install_step
from nm_bridge.knx_entity_plan import build
from nm_bridge.missing_ha_generator import fingerprint


class InstallStepTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = patch.object(widget_layout, 'WIDGET_PATH', Path(self.directory.name) / 'widgets.json')
        self.path.start()
        self.addCleanup(self.path.stop)
        widget_layout.save_layout({'version': 1, 'confirm': True, 'project': 'a'*64,
            'widgets': [{'type': 'light', 'name': name, 'fields': {'command': ga}}
                        for name, ga in [('Luce A', '1/1/1'), ('Luce B', '1/1/2')]]})

    def payload(self, index):
        layout = widget_layout.read_layout()
        w = layout['widgets'][index]
        review = {'source_fingerprint': fingerprint(layout), 'devices': [
            {'index': index, 'approved': True, 'name': w['name'], 'fields': w['fields']}]}
        plan = build(layout, review)
        return {'review': review, 'source_fingerprint': fingerprint(layout), 'confirm': True,
                'backup_confirmed': True, 'ets_confirmed': True, 'call_index': 0, 'expected_call': plan['calls'][0]}

    def create(self, layout, payload):
        # Exercise the real stale-layout and already-linked checks, without HA.
        build(layout, payload['review'])
        return {'created': True, 'entity_id': 'light.test_' + str(payload['review']['devices'][0]['index'])}

    def test_sequence_persists_each_association_and_rejects_retry(self):
        first = self.payload(0)
        old_second = self.payload(1)
        result = install_step(first, create=self.create)
        self.assertTrue(result['linked'])
        self.assertEqual(result['source_fingerprint'], fingerprint(widget_layout.read_layout()))
        for stale in (first, old_second):
            with self.assertRaises(ValueError):
                install_step(stale, create=self.create)
        install_step(self.payload(1), create=self.create)
        self.assertEqual([w['entity_id'] for w in widget_layout.read_layout()['widgets']], ['light.test_0', 'light.test_1'])

    def test_failure_keeps_earlier_success(self):
        install_step(self.payload(0), create=self.create)
        with self.assertRaises(OSError):
            install_step(self.payload(1), create=lambda *_: (_ for _ in ()).throw(OSError('Disconnected')))
        self.assertEqual(widget_layout.read_layout()['widgets'][0]['entity_id'], 'light.test_0')
        self.assertEqual(widget_layout.read_layout()['widgets'][1]['entity_id'], '')

    def test_save_failure_returns_created_entity_and_stops(self):
        payload = self.payload(0)
        with patch('nm_bridge.knx_install.save_layout', side_effect=OSError('disk full')):
            result = install_step(payload, create=self.create)
        self.assertTrue(result['created'])
        self.assertTrue(result['stop'])
        self.assertFalse(result['linked'])
        self.assertEqual(result['entity_id'], 'light.test_0')
