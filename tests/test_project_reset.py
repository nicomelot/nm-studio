import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nm_bridge.control_engine import ControlEngine
from nm_bridge.climate_cards import key
from nm_bridge.project_reset import ProjectReset

PROJECT = 'a' * 64
OTHER = 'b' * 64


class FakeHA:
    def __init__(self):
        ident = key(PROJECT, 'light.nm_lab_aaaaaaaaaaaa_luce')
        self.helpers = {'input_boolean': [{'id': 'nm_favorite_' + ident}, {'id': 'philips_external'}],
                        'input_number': [{'id': 'nm_favorite_order_' + ident, 'min': 0, 'max': 1000000000}],
                        'input_text': [{'id': 'nm_week_' + ident + '_commit', 'max': 255}]}
        self.states = [{'entity_id': 'light.philips', 'state': 'on', 'attributes': {}},
                       {'entity_id': 'input_text.nm_week_' + ident + '_commit', 'state': '{"enabled":true}'}]
        self.dashboards = {
            'nm-studio-casa-aaaaaaaaaaaa': {'title': 'SIM · Casa', 'views': [{'cards': [{'type': 'custom:nm-device-card', 'project': PROJECT, 'entity': 'light.nm_lab_aaaaaaaaaaaa_luce'}]}]},
            'personale': {'views': [{'cards': [{'type': 'custom:nm-device-card', 'project': PROJECT}, {'type': 'tile', 'entity': 'light.philips'}]}]},
            'nm-studio-schema-legacy': {'views': [{'cards': [{'type': 'custom:nm-floorplan-card', 'title': 'SIM · Centrale'}]}]},
            'nm-studio-casa-bbbbbbbbbbbb': {'views': [{'cards': [{'type': 'custom:nm-device-card', 'project': OTHER}]}]},
        }
        self.calls = []
        self.fail_once = False
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def call(self, method, **args):
        self.calls.append((method, copy.deepcopy(args)))
        if method == 'get_states': return copy.deepcopy(self.states)
        if method == 'lovelace/dashboards/list':
            return [{'id': p, 'url_path': p, 'mode': 'storage', 'title': c.get('title', p)} for p, c in self.dashboards.items()]
        if method == 'lovelace/config':
            if 'url_path' not in args:
                error = ValueError('No default dashboard'); error.code = 'config_not_found'; raise error
            return copy.deepcopy(self.dashboards[args['url_path']])
        if method == 'lovelace/config/save': self.dashboards[args['url_path']] = copy.deepcopy(args['config']); return {}
        if method == 'lovelace/dashboards/delete': del self.dashboards[args['dashboard_id']]; return {}
        domain, action = method.split('/')
        if action == 'list' and domain in self.helpers: return copy.deepcopy(self.helpers[domain])
        if action == 'delete' and domain in self.helpers:
            self.helpers[domain] = [h for h in self.helpers[domain] if h['id'] != args[domain + '_id']]
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError('Risposta persa dopo cancellazione aiutante')
            return {}
        raise AssertionError('Operazione non consentita nel simulatore: ' + method)


def fixture(root):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    config = root / 'ha'; config.mkdir(exist_ok=True)
    def save(name, data):
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data), encoding='utf-8')
    save('nm_knx_widget_layout.json', {'version': 1, 'project': PROJECT, 'rooms': ['SIM'], 'widgets': []})
    save('nm_control_automations.json', {'version': 1, 'revision': 1, 'projects': {PROJECT: []},
                                      'presence': {PROJECT: {'enabled': False}}, 'button_links': {PROJECT: []}})
    save('diagrams_' + PROJECT + '.json', {'plans': [{'name': 'SIM · Centrale'}]})
    save('nm_projects/' + PROJECT + '.json', {'label': 'SIM · Reset'})
    ident = key(PROJECT, 'light.nm_lab_aaaaaaaaaaaa_luce')
    save('nm_climate_cards.json', {ident: {'project': PROJECT, 'entity': 'light.nm_lab_aaaaaaaaaaaa_luce',
                                        'days': [], 'commit': 'input_text.nm_week_' + ident + '_commit'}})
    save('nm_floorplans.json', {'plans': [{'name': 'SIM · Planimetria'}]})
    ha = FakeHA()
    def layout():
        p = root / 'nm_knx_widget_layout.json'
        return json.loads(p.read_text()) if p.exists() else {'project': '', 'widgets': []}
    engine = ControlEngine(root, layout_provider=layout, connection_factory=lambda: ha)
    return ProjectReset(engine, config_root=config), ha


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.reset, self.ha = fixture(self.tmp.name)
        self.request = {'project': PROJECT}
    def prepared(self):
        review = self.reset.handle(self.request)
        backup = self.reset.handle({**self.request, 'operation': 'backup', 'fingerprint': review['fingerprint']})
        return {**self.request, 'operation': 'apply', 'fingerprint': review['fingerprint'],
                'backup_id': backup['backup_id'], 'backup_downloaded': True, 'confirm': True, 'phrase': review['phrase']}
    def test_preview_is_read_only_and_complete_reset_preserves_external_and_other_project(self):
        before = copy.deepcopy(self.ha.dashboards)
        review = self.reset.handle(self.request)
        self.assertEqual(before, self.ha.dashboards)
        self.assertFalse(any('/delete' in m or '/save' in m for m, _ in self.ha.calls))
        self.assertEqual(len(review['helpers']), 3)
        request = self.prepared(); result = self.reset.handle(request)
        self.assertTrue(result['complete']); self.assertIsNone(self.reset.pending())
        self.assertEqual(self.reset.e.layout_provider()['project'], '')
        self.assertTrue(self.reset.backup_path(request['backup_id']).exists())
        self.assertNotIn('nm-studio-casa-aaaaaaaaaaaa', self.ha.dashboards)
        self.assertEqual(self.ha.dashboards['personale']['views'][0]['cards'], [{'type': 'tile', 'entity': 'light.philips'}])
        self.assertEqual(before['nm-studio-casa-bbbbbbbbbbbb'], self.ha.dashboards['nm-studio-casa-bbbbbbbbbbbb'])
        self.assertIn('nm-studio-schema-legacy', self.ha.dashboards)
        self.assertEqual(self.ha.helpers['input_boolean'], [{'id': 'philips_external'}])
        self.assertFalse(any(m == 'call_service' for m, _ in self.ha.calls))
    def test_confirmations_and_backup_required(self):
        request = self.prepared()
        for field, value in [('confirm', False), ('phrase', 'AZZERA'), ('backup_downloaded', False), ('backup_id', 'bad')]:
            with self.assertRaises(ValueError): self.reset.handle({**request, field: value})
        self.assertFalse(any('/delete' in m for m, _ in self.ha.calls))
    def test_stale_preview_and_backup_failure_do_not_delete(self):
        request = self.prepared(); self.ha.dashboards['personale']['title'] = 'Personalizzazione nuova'
        with self.assertRaisesRegex(ValueError, 'Dati cambiati'): self.reset.handle(request)
        review = self.reset.handle(self.request)
        with patch('nm_bridge.project_reset.zipfile.ZipFile', side_effect=OSError('Disco pieno')):
            with self.assertRaises(OSError): self.reset.handle({**self.request, 'operation':'backup', 'fingerprint':review['fingerprint']})
        self.assertFalse(any('/delete' in m for m, _ in self.ha.calls))
    def test_interrupted_reset_suspends_commands_and_resumes_after_restart(self):
        request = self.prepared(); self.ha.fail_once = True
        result = self.reset.handle(request); self.assertFalse(result['complete'])
        self.assertTrue(self.reset.e.reset_pending())
        with self.assertRaisesRegex(ValueError, 'sospesi'):
            self.reset.e.execute({'project': PROJECT}, {}, [], 'unsafe')
        self.reset.e.tick()
        replacement = ProjectReset(self.reset.e, config_root=self.reset.config_root)
        self.assertTrue(replacement.handle({**request, 'operation':'resume'})['complete'])
        self.assertFalse(self.reset.e.reset_pending())
    def test_legacy_page_requires_explicit_selection_and_foreign_rejected(self):
        with self.assertRaises(ValueError):
            self.reset.handle({**self.request, 'legacy_dashboards':['nm-studio-casa-bbbbbbbbbbbb']})
        review = self.reset.handle({**self.request, 'legacy_dashboards':['nm-studio-schema-legacy']})
        self.assertTrue(any(d['path']=='nm-studio-schema-legacy' and d['action']=='Elimina pagina' for d in review['dashboards']))
    def test_resume_rechecks_previously_completed_shared_dashboard(self):
        request = self.prepared(); self.ha.fail_once = True
        self.assertFalse(self.reset.handle(request)['complete'])
        self.ha.dashboards['personale']['title'] = 'Changed while interrupted'
        result = self.reset.handle({**request, 'operation': 'resume'})
        self.assertFalse(result['complete'])
        self.assertIn('Pagina modificata', result['pending']['error'])
        self.assertTrue(self.reset.e.reset_pending())
    def test_running_momentary_and_presence_block_deletion(self):
        with self.reset.e.db() as db:
            db.execute('INSERT INTO holds VALUES(?,?,?,?,?,?,?)', ('x', PROJECT, 'd', 'switch.demo', 0, 0, 'active'))
        review = self.reset.handle(self.request)
        self.assertTrue(review['blockers'])
        with self.assertRaises(ValueError): self.reset.handle({**self.request, 'operation':'backup', 'fingerprint':review['fingerprint']})
    def test_backup_paths_reject_traversal(self):
        with self.assertRaises(ValueError): self.reset.backup_path('../outside')
        with self.assertRaises(ValueError): self.reset.checked(self.reset.root.parent / 'outside')

if __name__ == '__main__': unittest.main()
