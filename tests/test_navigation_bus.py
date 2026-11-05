import json
import tempfile
import unittest
from pathlib import Path
from nm_bridge.lab_dashboard import preview, publish
from nm_bridge.bus_recorder import Recorder, addresses
from test_lab_devices import project, inventory
from test_dashboard_publisher import FakeClient


class NavigationTests(unittest.TestCase):
    def test_links_rooms_categories_and_isolation(self):
        request = project(("light", "cover", "climate", "sensor"))
        for i, d in enumerate(request['devices']):
            d['room'] = 'Casa / Piano / Stanza ' + str(i)
        result = preview(request, inventory(request))
        views = result['dashboard']['views']
        self.assertEqual([v['title'] for v in views[:3]], ['Home', 'Ambienti', 'Funzioni'])
        paths = {v['path'] for v in views}
        self.assertEqual(len(paths), len(views))
        def visit(obj):
            if isinstance(obj, dict):
                if 'navigation_path' in obj:
                    self.assertIn(obj['navigation_path'].split('/')[-1], paths)
                if 'entity' in obj:
                    self.assertIn('.nm_lab_', obj['entity'])
                for value in obj.values(): visit(value)
            elif isinstance(obj, list):
                for value in obj: visit(value)
        visit(views)
        self.assertTrue(all(v.get('subview') for v in views[3:]))
        self.assertNotIn('Antifurto', json.dumps(views))
        client = FakeClient()
        publish({**request, 'confirm': True, 'expected_fingerprint': result['fingerprint']}, inventory(request), lambda: client)
        self.assertGreater(len(client.saved['views']), 8)


class BusTests(unittest.TestCase):
    def test_ingress_routes_require_confirmation(self):
        from test_lab_http import request
        self.assertEqual(request('/bus-log/start', {'addresses': ['1/2/3']}, '127.0.0.1')['status'], 403)
        self.assertEqual(request('/bus-log/start', {'addresses': ['1/2/3']})['status'], 400)

    def test_validation(self):
        for bad in (None, [], ['32/0/0'], ['1/8/0'], ['1/2/256'], ['*/*/*']):
            with self.assertRaises(ValueError): addresses(bad)

    def test_persistence_filter_raw_and_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bus.sqlite'
            r = Recorder(path)
            r.selected = ['1/2/3']
            event = {'time_fired': '2026-11-03T15:00:00Z', 'data': {'destination': '1/2/3', 'source': '1.1.10', 'data': 1, 'telegramtype': 'GroupValueWrite'}}
            r.record(event)
            r.record({'data': {'destination': '1/2/4'}})
            saved = Recorder(path).snapshot()['items']
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]['data'], 1)
            self.assertIsNone(saved[0]['value'])
            self.assertEqual(r.snapshot('1/2/4')['items'], [])
            with r._db() as db:
                db.executemany('INSERT INTO events(destination,payload,received) VALUES (?,?,?)', [('1/2/3', json.dumps(saved[0]), __import__('time').time())] * 10010)
            r.record(event)
            with r._db() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 10000)

    def test_only_local_event_registration_and_subscription(self):
        with tempfile.TemporaryDirectory() as folder:
            class Client:
                calls = []
                def __enter__(self): return self
                def __exit__(self, *args): pass
                @property
                def connection(self): return self
                def settimeout(self, value): pass
                def call(self, command, **kw): self.calls.append((command, kw))
                def _receive(self):
                    r.stop_event.set()
                    return {'type': 'event', 'event': {'data': {'destination': '1/2/3', 'data': 0}}}
            client = Client()
            r = Recorder(Path(folder) / 'events.db', lambda: client)
            r.selected = ['1/2/3']
            r._run()
            self.assertEqual([c[0] for c in client.calls], ['subscribe_events', 'call_service'])
            self.assertEqual(client.calls[1][1]['service'], 'event_register')
            self.assertEqual(r.status, 'stopped')
            self.assertEqual(len(r.snapshot()['items']), 1)


class BusQueryTests(unittest.TestCase):
    def test_retention_source_time_and_pagination(self):
        import time
        from datetime import datetime, timezone, timedelta
        with tempfile.TemporaryDirectory() as folder:
            r=Recorder(Path(folder)/'events.db'); r.selected=['1/2/3']
            r.record({'data':{'destination':'1/2/3','source':'1.1.10','value':1}})
            with r._db() as db:
                payload=db.execute('SELECT payload FROM events').fetchone()[0]
                db.execute('INSERT INTO events(destination,payload,received) VALUES (?,?,?)',('1/2/3',payload,time.time()-49*3600))
                db.executemany('INSERT INTO events(destination,payload,received) VALUES (?,?,?)',[('1/2/3',payload,time.time())]*501)
            page=r.snapshot(source='1.1.10'); self.assertEqual(len(page['items']),500)
            self.assertEqual(len(r.snapshot(before=page['next_cursor'])['items']),2)
            self.assertEqual(r.snapshot(source='1.1.11')['items'],[])
            future=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
            self.assertEqual(r.snapshot(start=future)['items'],[])
            with r._db() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],502)
            with self.assertRaises(ValueError): r.snapshot(start='2026-11-05T10:00:00')
