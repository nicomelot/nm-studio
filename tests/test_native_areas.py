import tempfile
import unittest
from pathlib import Path
from nm_bridge.native_areas import sync
from nm_bridge.missing_ha_generator import fingerprint


class Registry:
    def __init__(self):
        self.areas = []
        self.floors = []
        self.entities = {'light.test': {'entity_id': 'light.test', 'area_id': None}}
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def call(self, method, **args):
        if method.endswith('/list'):
            return list(self.areas if '/area_' in method else self.floors)
        if method.endswith('/get'):
            return self.entities[args['entity_id']].copy()
        self.writes.append((method, args))
        if method.endswith('/create'):
            target, key = (self.areas, 'area_id') if '/area_' in method else (self.floors, 'floor_id')
            record = {key: str(len(target)+1), **args}
            target.append(record)
            return record
        if method == 'config/entity_registry/update':
            self.entities[args['entity_id']].update(args)
            return self.entities[args['entity_id']]
        raise AssertionError(method)


class NativeAreaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'mapping.json'
        self.registry = Registry()
        self.layout = {'project': 'a'*64, 'structure': [
            {'id':'b','parent':None,'type':'building','name':'Casa'},
            {'id':'r','parent':'b','type':'room','name':'Sala'}],
            'widgets':[{'entity_id':'light.test','room':'Casa / Sala'}]}

    def run_sync(self):
        return sync(self.layout, {'confirm': True, 'source_fingerprint': fingerprint(self.layout)},
                    connection_factory=lambda:self.registry, mapping_path=self.path)

    def test_idempotent_without_invented_floor(self):
        result = self.run_sync()
        self.assertEqual(result['assigned'], 1)
        self.assertEqual(self.registry.floors, [])
        count = len(self.registry.writes)
        self.run_sync()
        self.assertEqual(len(self.registry.writes), count)
        self.assertEqual(self.registry.areas[0]['name'], 'Sala')

    def test_preserve_explicit_assignment_and_mapped_area_on_rename(self):
        self.registry.entities['light.test']['area_id'] = 'customer_choice'
        self.assertTrue(self.run_sync()['notices'])
        self.layout['structure'][1]['name'] = 'Salotto'
        self.layout['widgets'][0]['room'] = 'Casa / Salotto'
        self.run_sync()
        self.assertEqual(len(self.registry.areas), 1)
        self.assertEqual(self.registry.entities['light.test']['area_id'], 'customer_choice')

    def test_stale_or_unconfirmed_request_never_opens_connection(self):
        for request in ({}, {'confirm':True,'source_fingerprint':'old'}):
            with self.assertRaises(ValueError):
                sync(self.layout, request, connection_factory=lambda:self.fail('must not connect'), mapping_path=self.path)
