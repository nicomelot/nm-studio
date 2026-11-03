import unittest
from nm_bridge.lab_dashboard import preview
from nm_bridge.lab_devices import build
from nm_bridge.dashboard_publisher import MAX_VIEWS
from test_lab_devices import project, inventory


def cards(view):
    return [card for section in view['sections'] for card in section['cards']]


class RoomDashboardTests(unittest.TestCase):
    def test_floor_zone_popup_and_separate_tools(self):
        request = project(('light', 'cover', 'climate', 'sensor', 'scene'))
        for item in request['devices']:
            item['room'] = 'Villa / PIANO INTERRATO / Bagno'
        result = preview(request, inventory(request))
        views = {v['path']: v for v in result['dashboard']['views']}
        floor_link = next(c for c in cards(views['ambienti']) if c['type'] == 'button')
        self.assertEqual(floor_link['name'], 'Interrato')
        floor = views[floor_link['tap_action']['navigation_path'].split('/')[-1]]
        zone_link = next(c for c in cards(floor) if c['type'] == 'button')
        self.assertEqual(zone_link['name'], 'Bagno')
        zone = views[zone_link['tap_action']['navigation_path'].split('/')[-1]]
        self.assertTrue(zone['back_path'].endswith('/' + floor['path']))
        tiles = [c for c in cards(zone) if c['type'] == 'tile']
        self.assertEqual({c['entity'] for c in tiles}, {m['entity_id'] for m in build(request)['manifest']})
        for card in tiles:
            self.assertEqual(card['tap_action'], {'action': 'more-info'})
            self.assertEqual(card['icon_tap_action'], {'action': 'more-info'})
            self.assertEqual(card['grid_options']['columns'], 12)
        self.assertFalse(any(c['type'] in ('entities', 'history-graph') for c in cards(zone)))
        graphs = [c for v in views.values() for c in cards(v) if c['type'] == 'history-graph']
        self.assertTrue(graphs)
        self.assertFalse(any(e.startswith('climate.') for c in graphs for e in c['entities']))
        helpers = [e['entity'] for c in cards(views['strumenti-lab']) if c['type'] == 'entities' for e in c['entities']]
        self.assertEqual(set(helpers), {e for m in build(request)['manifest'] for e in m['controls']})

    def test_buildings_unassigned_and_floor_functions_are_not_merged(self):
        request = project(('light',) * 5)
        names = ['A / PIANO TERRA / Bagno', 'B / PIANO TERRA / Bagno',
                 'A / PIANO TERRA', 'Bagno', 'A / Ufficio']
        for item, room in zip(request['devices'], names):
            item['room'] = room
        result = preview(request, inventory(request))
        views = result['dashboard']['views']
        zones = [v for v in views if v['path'].startswith('stanza-')]
        self.assertEqual(len(zones), 5)
        self.assertEqual(len({v['path'] for v in zones}), 5)
        self.assertIn('Generali', [v['title'] for v in zones])
        self.assertIn('Ufficio', [v['title'] for v in zones])
        floor_names = [c['name'] for c in cards(views[1]) if c['type'] == 'button']
        self.assertIn('A · Terra', floor_names)
        self.assertIn('B · Terra', floor_names)
        self.assertIn('Altre zone', floor_names)
        request['devices'].reverse()
        self.assertEqual(result['fingerprint'], preview(request, inventory(request))['fingerprint'])

    def test_routes_and_supported_maximum(self):
        request = project(('light',) * 200)
        for i, item in enumerate(request['devices']):
            item['room'] = f'Villa / Piano {i} / Zona'
        views = preview(request, inventory(request))['dashboard']['views']
        self.assertLessEqual(len(views), MAX_VIEWS)
        paths = {v['path'] for v in views}
        self.assertEqual(len(paths), len(views))
        for v in views:
            if 'back_path' in v:
                self.assertIn(v['back_path'].split('/')[-1], paths)
            for card in cards(v):
                action = card.get('tap_action', {})
                if action.get('action') == 'navigate':
                    self.assertIn(action['navigation_path'].split('/')[-1], paths)
        old = {v['title']: v['path'] for v in views if v['path'].startswith('piano-')}
        request['devices'].pop(0)
        updated = preview(request, inventory(request))['dashboard']['views']
        for v in updated:
            if v['path'].startswith('piano-'):
                self.assertEqual(v['path'], old[v['title']])
