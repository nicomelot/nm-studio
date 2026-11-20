import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nm_bridge.dashboard_publisher import (PublishError, _replacement, publish_generated,
                                              preview_generated_update, update_generated)
from nm_bridge.ets_dashboard import preview
from nm_bridge.ets_import import preview as parse_ets
from nm_bridge.lab_devices import candidates
from nm_bridge.lovelace_generator import generate
from nm_bridge.project_sessions import Sessions
from test_dashboard_publisher import FakeClient
from test_ets_hvac_devices import fixture


class EtsDashboardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        sessions = Sessions(self.root / 'projects', room_provider=lambda: {})
        data = parse_ets(fixture())
        data['lab_candidates'] = candidates(data)
        data = sessions.prepare(data)
        self.project = data['project_key']
        sessions.save({'confirm': True, 'token': data['session_token'], 'label': 'Edificio prova',
                       'reviews': [{**row, 'selected': False} for row in data['lab_candidates']]})
        self.record = sessions.read(self.project)
        self.draft = preview(self.project, self.record)
        self.request = {'confirm': True, 'url_path': self.draft['url_path'],
                        'title': self.draft['title'], 'expected_fingerprint': self.draft['fingerprint']}

    def test_saved_ets_gives_room_and_function_views_without_live_cards(self):
        self.assertEqual(self.draft['summary'], {'tiles': 0, 'planned': 6, 'rooms': 6,
                                                'functions': 1, 'climate': 3, 'gateways': 2, 'shared': 4})
        views = self.draft['dashboard']['views']
        self.assertTrue({'Sala', 'Cucina', 'Locale tecnico A', 'Locale tecnico B'}.issubset(v['title'] for v in views))
        cards = [card for view in views for section in view['sections'] for card in section['cards']]
        self.assertTrue(any('GA condivisi' in card.get('heading', '') for card in cards))
        self.assertTrue(all(card.get('tap_action', {}).get('action', 'none') in ('none', 'navigate') for card in cards))
        self.assertFalse(any('entity' in card or 'entities' in card for card in cards))

    def test_draft_publish_is_create_only_and_honors_review(self):
        client = FakeClient()
        with patch('nm_bridge.dashboard_publisher.BACKUP_DIR', self.root):
            with self.assertRaisesRegex(PublishError, 'Nessuna entità'):
                publish_generated(self.request, self.draft, lambda: client)
            with self.assertRaisesRegex(PublishError, 'Anteprima'):
                publish_generated({**self.request, 'expected_fingerprint': 'expired'},
                                  self.draft, lambda: client, offline=True)
            result = publish_generated(self.request, self.draft, lambda: client, offline=True)
            self.assertTrue(result['created'])
            client.existing.append(result['url_path'])
            with self.assertRaisesRegex(PublishError, 'già esistente'):
                publish_generated(self.request, self.draft, lambda: client, offline=True)
            self.assertEqual(sum(method == 'lovelace/config/save' for method, _ in client.calls), 1)

    def test_online_review_reuses_path_and_keeps_manual_views(self):
        layout = {'project': self.project, 'widgets': [{
            'type': 'light', 'name': 'Luce corridoio', 'room': 'Progetto / Corridoio',
            'entity_id': 'light.corridoio',
        }]}
        online = generate(layout, [{'entity_id': 'light.corridoio'}])
        self.assertEqual(online['url_path'], self.draft['url_path'])
        current = copy.deepcopy(self.draft['dashboard'])
        manual = {'title': 'Personalizzata', 'path': 'personale', 'cards': []}
        current['views'].append(manual)
        with patch('nm_bridge.dashboard_publisher.BACKUP_DIR', self.root):
            publish_generated(self.request, self.draft, FakeClient, offline=True)
            result = _replacement(online, current, self.root)
        self.assertIn(manual, result['views'])
        self.assertTrue(any(c.get('entity') == 'light.corridoio' for v in result['views']
                            for section in v.get('sections', []) for c in section['cards']))

    def test_climate_upgrade_preserves_manual_views_and_does_not_provision_entities(self):
        client = FakeClient()
        popup = preview(self.project, self.record, climate_popups=True)
        with patch('nm_bridge.dashboard_publisher.BACKUP_DIR', self.root), patch(
            'nm_bridge.dashboard_publisher.install_resource'
        ) as install:
            publish_generated(self.request, self.draft, lambda: client, offline=True)
            client.existing.append(popup['url_path'])
            manual = {'title': 'Personalizzata', 'path': 'personale', 'cards': []}
            client.saved['views'].append(manual)
            diff = preview_generated_update(self.request, popup, lambda: client)
            self.assertTrue(diff['changed'])
            request = {**self.request, 'expected_fingerprint': diff['expected_fingerprint'],
                       'expected_current': diff['expected_current']}
            self.assertTrue(update_generated(request, popup, lambda: client, offline=True)['updated'])
            install.assert_called_once_with(client, climate_only=True)
        self.assertIn(manual, client.saved['views'])
        cards = [card for view in client.saved['views'] for section in view.get('sections', [])
                 for card in section['cards'] if card['type'] == 'custom:nm-climate-card']
        self.assertEqual({c['commissioning']['individual_address'] for c in cards}, {'1.1.51', '1.1.52', '1.1.53'})
        self.assertTrue(all('entity' not in card and 'schedule' not in card for card in cards))
        self.assertTrue(all(method.startswith('lovelace/') for method, _ in client.calls))
