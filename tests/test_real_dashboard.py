import copy
import json
import unittest

from nm_bridge.entity_matcher import suggest
from nm_bridge.lovelace_generator import generate
from nm_bridge.dashboard_publisher import publish
from test_dashboard_publisher import FakeClient


class RealDashboardTests(unittest.TestCase):
    def setUp(self):
        self.widget = {'name': 'L5', 'type': 'light', 'room': 'Nuova FR / Piano Terra / Ufficio',
                       'entity_id': 'light.nm_lab_77afd65a7b30_1_1_8'}
        self.layout = {'project': 'magazzino', 'widgets': [self.widget]}
        self.entities = [
            {'entity_id': self.widget['entity_id'], 'name': 'L5', 'state': 'off'},
            {'entity_id': 'light.fuori_ufficio_l5', 'name': 'FUORI UFFICIO - L5', 'state': 'on'},
            {'entity_id': 'light.ufficio_l15', 'name': 'UFFICIO - L15', 'state': 'off'}]

    def test_replace_lab_with_real_l5_not_l15(self):
        original = copy.deepcopy(self.layout)
        result = suggest(self.layout, self.entities)
        proposal = result['proposals'][0]
        self.assertEqual(proposal['suggested_entity_id'], 'light.fuori_ufficio_l5')
        self.assertEqual(proposal['current_entity_id'], '')
        self.assertEqual(proposal['replaced_lab_entity_id'], self.widget['entity_id'])
        self.assertEqual(result['linked'], 0)
        self.assertNotIn('nm_lab_', json.dumps(proposal['compatible_entities']))
        self.assertEqual(self.layout, original)

    def test_ambiguous_names_are_not_automatically_proposed(self):
        self.entities.append({'entity_id': 'light.altro_l5', 'name': 'ALTRO L5'})
        self.assertEqual(suggest(self.layout, self.entities)['proposals'][0]['suggested_entity_id'], '')

    def test_valid_existing_association_is_preserved(self):
        self.widget['entity_id'] = 'light.fuori_ufficio_l5'
        proposal = suggest(self.layout, self.entities)['proposals'][0]
        self.assertEqual(proposal['current_entity_id'], 'light.fuori_ufficio_l5')
        self.assertEqual(proposal['suggested_entity_id'], '')

    def test_lab_cannot_be_published_even_when_it_exists(self):
        preview = generate(self.layout, self.entities)
        self.assertEqual(preview['summary']['tiles'], 0)
        self.assertIn('LAB', preview['warnings'][0]['reason'])
        fake = FakeClient()
        with self.assertRaises(ValueError):
            publish({'confirm': True, 'title': 'Reale', 'url_path': 'nm-studio-real',
                     'expected_fingerprint': preview['fingerprint']}, self.layout,
                    self.entities, client_factory=lambda: fake)
        self.assertEqual(fake.calls, [])

    def test_published_navigation_and_popups_use_real_entity(self):
        self.widget['entity_id'] = 'light.fuori_ufficio_l5'
        preview = generate(self.layout, self.entities)
        fake = FakeClient()
        publish({'confirm': True, 'title': 'Magazzino reale', 'url_path': 'nm-studio-magazzino',
                 'expected_fingerprint': preview['fingerprint']}, self.layout,
                self.entities, client_factory=lambda: fake)
        config = fake.saved
        self.assertNotIn('nm_lab_', json.dumps(config))
        self.assertNotIn('Laboratorio', json.dumps(config))
        self.assertEqual(config['title'], 'Magazzino reale')
        routes = {'/nm-studio-magazzino/' + v['path'] for v in config['views']}
        tiles, links = [], []
        def walk(value):
            if isinstance(value, dict):
                if value.get('type') == 'tile':
                    tiles.append(value)
                for k, v in value.items():
                    if k in ('navigation_path', 'back_path'):
                        links.append(v)
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
        walk(config)
        self.assertTrue(links)
        self.assertTrue(set(links) <= routes)
        self.assertTrue(tiles)
        for tile in tiles:
            self.assertEqual(tile['entity'], 'light.fuori_ufficio_l5')
            self.assertEqual(tile['tap_action'], {'action': 'more-info'})
        titles = {v['title'] for v in config['views']}
        self.assertTrue({'Terra', 'Ufficio', 'Luci'} <= titles)


if __name__ == '__main__':
    unittest.main()
