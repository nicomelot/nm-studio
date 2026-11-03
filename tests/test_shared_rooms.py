import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nm_bridge import widget_layout
from nm_bridge.project_sessions import Sessions
from test_project_sessions import imported, save_request


class SharedRoomsTests(unittest.TestCase):
    def catalog(self):
        return {'confirm': True, 'version': 1, 'project': 'a'*64,
                'structure': [{'id': 'b', 'parent': None, 'type': 'building', 'name': 'Casa'},
                              {'id': 'f', 'parent': 'b', 'type': 'floor', 'name': 'Terra'},
                              {'id': 'r', 'parent': 'f', 'type': 'room', 'name': 'Studio'}],
                'rooms': ['Casa / Terra / Studio'], 'widgets': [],
                'room_aliases': {'Casa / Terra / Ufficio': 'Casa / Terra / Studio'}}

    def test_rename_survives_save_restart_resume_and_reimport(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(widget_layout, 'WIDGET_PATH', Path(folder) / 'widgets.json'):
            sessions = Sessions(Path(folder)/'projects')
            source = imported();source['lab_candidates'][0]['room'] = 'Casa / Terra / Ufficio'
            data = sessions.prepare(source);sessions.save(save_request(data))
            widget_layout.save_layout(self.catalog())
            resumed = Sessions(Path(folder)/'projects').resume('a'*64)
            self.assertEqual(resumed['lab_candidates'][0]['room'], 'Casa / Terra / Studio')
            self.assertTrue(resumed['lab_candidates'][0]['selected'])
            self.assertEqual(resumed['session_changes']['changed'], [])
            self.assertEqual(sessions.prepare(source)['lab_candidates'][0]['room'], 'Casa / Terra / Studio')
            self.assertEqual(source['lab_candidates'][0]['room'], 'Casa / Terra / Ufficio')

    def test_exact_paths_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            sessions = Sessions(folder, room_provider=self.catalog)
            source = imported();source['lab_candidates'][0]['room'] = 'Casa / Primo / Ufficio'
            self.assertEqual(sessions.prepare(source)['lab_candidates'][0]['room'], 'Casa / Primo / Ufficio')
            source['project_key'] = 'b'*64;source['lab_candidates'][0]['room'] = 'Casa / Terra / Ufficio'
            self.assertEqual(sessions.prepare(source)['lab_candidates'][0]['room'], 'Casa / Terra / Ufficio')

    def test_existing_rename_can_use_unambiguous_widget_command(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = self.catalog();catalog['room_aliases'] = {}
            catalog['widgets'] = [{'room': 'Casa / Terra / Studio', 'fields': {'command': '1/0/0'}}]
            sessions = Sessions(folder, room_provider=lambda: catalog)
            self.assertEqual(sessions.prepare(imported())['lab_candidates'][0]['room'], 'Casa / Terra / Studio')
            catalog['rooms'].append('Casa / Terra / Altro')
            catalog['widgets'].append({'room':'Casa / Terra / Altro','fields':{'command':'1/0/0'}})
            self.assertEqual(sessions.prepare(imported())['lab_candidates'][0]['room'], 'Magazzino')

    def test_invalid_alias_is_rejected_and_does_not_replace_layout(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(widget_layout, 'WIDGET_PATH', Path(folder)/'widgets.json'):
            good=self.catalog();widget_layout.save_layout(good);before=widget_layout.WIDGET_PATH.read_bytes()
            bad={**good,'room_aliases':{'Old':'Not in structure'}}
            with self.assertRaises(ValueError):widget_layout.save_layout(bad)
            self.assertEqual(widget_layout.WIDGET_PATH.read_bytes(),before)
