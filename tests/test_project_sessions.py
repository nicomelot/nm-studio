import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nm_bridge.project_sessions import Sessions
from nm_bridge.lab_dashboard import preview, inspect_existing, update
from nm_bridge.knx_history import query
from test_lab_devices import project, inventory
from test_dashboard_publisher import FakeClient


def imported():
    return {'project_key': 'a' * 64, 'lab_candidates': project(('light', 'cover'))['devices'],
            'building': [], 'suggestions': [], 'addresses': [], 'total': 2}


def save_request(data):
    return {'confirm': True, 'token': data['session_token'], 'expected_revision': data['session_revision'],
            'label': 'Magazzino', 'reviews': data['lab_candidates']}


class SessionTests(unittest.TestCase):
    def test_save_resume_changes_and_isolated_projects(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder)
            data = sessions.prepare(imported())
            data['lab_candidates'][0]['room'] = 'Primo / Ufficio'
            data['lab_candidates'][0]['name'] = 'Luce corretta'
            sessions.save(save_request(data))
            restored = Sessions(folder).resume('a' * 64)
            self.assertEqual(restored['lab_candidates'][0]['name'], 'Luce corretta')
            self.assertTrue(restored['lab_candidates'][0]['selected'])
            modified = imported()
            modified['lab_candidates'][0]['name'] = 'Nome ETS cambiato'
            modified['lab_candidates'].pop()
            modified['lab_candidates'].append({'command': '1/0/5', 'kind': 'sensor', 'name': 'Nuovo', 'room': 'Sala'})
            reimport = sessions.prepare(modified)
            self.assertEqual(reimport['session_changes']['changed'], ['1/0/0'])
            self.assertEqual(reimport['session_changes']['removed'], ['1/0/1'])
            self.assertEqual(reimport['session_changes']['added'], ['1/0/5'])
            self.assertFalse(reimport['lab_candidates'][0]['selected'])
            self.assertFalse(reimport['lab_candidates'][1]['selected'])
            self.assertEqual(reimport['lab_candidates'][0]['room'], 'Primo / Ufficio')
            other = imported();other['project_key'] = 'b' * 64
            self.assertNotEqual(sessions.prepare(other)['lab_candidates'][0]['room'], 'Primo / Ufficio')
            sessions.save(save_request(reimport))
            self.assertTrue((Path(folder) / ('a'*64 + '.bak')).exists())

    def test_stale_duplicate_and_unconfirmed_saves_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder)
            data = sessions.prepare(imported())
            payload = save_request(data)
            with self.assertRaises(ValueError): sessions.save({**payload, 'confirm': False})
            with self.assertRaises(ValueError): sessions.save({**payload, 'reviews': [payload['reviews'][0]]*2})
            with self.assertRaises(ValueError): sessions.read('../configuration')
            sessions.save(payload)
            with self.assertRaisesRegex(ValueError, 'altra finestra'): sessions.save(payload)

    def test_atomic_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder)
            data = sessions.prepare(imported());sessions.save(save_request(data))
            old = sessions.read('a'*64)
            current = sessions.resume('a'*64);current['lab_candidates'][0]['room'] = 'Changed'
            with patch('nm_bridge.project_sessions.os.replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError): sessions.save(save_request(current))
            self.assertEqual(sessions.read('a'*64), old)

    def test_changed_feedback_requires_review_even_with_same_lab_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder)
            original = imported()
            original['suggestions'] = [{'command': '1/0/0', 'feedback': '1/0/9'}]
            data = sessions.prepare(original); sessions.save(save_request(data))
            original['suggestions'][0]['feedback'] = '1/0/10'
            revised = sessions.prepare(original)
            self.assertEqual(revised['session_changes']['changed'], ['1/0/0'])
            self.assertFalse(revised['lab_candidates'][0]['selected'])

    def test_http_save_and_resume_without_bus_access(self):
        import bridge
        from test_lab_http import request
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder); data = sessions.prepare(imported())
            with patch.object(bridge, 'PROJECTS', sessions):
                self.assertEqual(request('/projects/save', save_request(data), '127.0.0.1')['status'], 403)
                result = request('/projects/save', save_request(data))
                self.assertEqual(result['status'], 200)
                self.assertTrue(result['data']['saved'])


class DashboardUpdateTests(unittest.TestCase):
    def test_update_with_backup_and_stale_guard(self):
        request = project(); states = inventory(request)
        generated = preview(request, states)
        client = FakeClient(existing=[generated['url_path']])
        original = {'views': [{'title': 'Personalizzata'}]}
        client.saved = copy.deepcopy(original)
        existing = inspect_existing(request, states, lambda: client)
        payload = {**request, 'confirm': True, 'expected_fingerprint': generated['fingerprint'],
                   'expected_existing_fingerprint': existing['fingerprint']}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): update({**payload, 'expected_existing_fingerprint': 'stale'}, states, lambda: client, folder)
            self.assertEqual(list(Path(folder).iterdir()), [])
            result = update(payload, states, lambda: client, folder)
            self.assertEqual(json.loads(Path(result['backup']).read_text(encoding='utf-8')), original)
            self.assertEqual(client.saved, generated['dashboard'])
            self.assertTrue(result['updated'])
        self.assertFalse(any('history-graph' in json.dumps(v) for v in generated['dashboard']['views']))

    def test_failed_backup_does_not_write_ha(self):
        request = project(); states = inventory(request); generated = preview(request, states)
        client = FakeClient(existing=[generated['url_path']]);client.saved={'views': []}
        existing = inspect_existing(request, states, lambda: client)
        with patch('nm_bridge.lab_dashboard.Path.mkdir', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                update({**request, 'confirm': True, 'expected_fingerprint': generated['fingerprint'],
                        'expected_existing_fingerprint': existing['fingerprint']}, states, lambda: client)
        self.assertFalse(any(name == 'lovelace/config/save' for name, _ in client.calls))


class HistoryTests(unittest.TestCase):
    def test_filters_window_and_read_only_calls(self):
        class Client(FakeClient):
            def call(self, method, **kw):
                self.calls.append((method, kw))
                return {'connection_info': {'telegram_retention': 3}} if method == 'knx/get_base_data' else {'telegrams': [], 'total_count': 0, 'limit_reached': False}
        client = Client()
        data = query({'ga': '1/2/3', 'source': '1.1.10', 'offset': 500}, lambda: client)
        self.assertTrue(data['available'])
        self.assertEqual([c[0] for c in client.calls], ['knx/get_base_data', 'knx/query_telegrams'])
        self.assertEqual(client.calls[1][1]['limit'], 500)
        self.assertEqual(client.calls[1][1]['sources'], ['1.1.10'])
        self.assertEqual(data['retention_days'], 3)
        from datetime import datetime
        self.assertEqual((datetime.fromisoformat(data['end']) - datetime.fromisoformat(data['start'])).total_seconds(), 48*3600)

    def test_denied_access_is_not_empty_success(self):
        client = FakeClient(fail='knx/get_base_data')
        data = query({}, lambda: client)
        self.assertFalse(data['available'])
        self.assertEqual(len(client.calls), 1)
        self.assertIn('permessi', data['note'])
        for payload in ({'ga': '32/1/0'}, {'offset': -1}, {'source': '16.1.1'}, {'end': '2026-11-01T12:00:00'}):
            with self.assertRaises(ValueError): query(payload, lambda: client)
