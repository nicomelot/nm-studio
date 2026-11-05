"""Publishing must never overwrite a Home Assistant dashboard."""

import unittest
from nm_bridge.dashboard_publisher import publish, PublishError, HAWebSocket
import json
from nm_bridge.lovelace_generator import generate


LAYOUT = {"rooms": ["Ufficio"], "structure": [], "widgets": [
    {"name": "L1", "type": "light", "room": "Ufficio", "entity_id": "light.l1"}]}
ENTITIES = [{"entity_id": "light.l1"}]
PAYLOAD = {"confirm": True, "title": "NM Studio Test", "url_path": "nm-studio-test",
           "expected_fingerprint": generate(LAYOUT, ENTITIES)["fingerprint"]}


class FakeClient:
    def __init__(self, existing=None, fail=None):
        self.existing = existing or []
        self.fail = fail
        self.calls = []
        self.saved = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def call(self, method, **kw):
        self.calls.append((method, kw))
        if method == self.fail:
            raise PublishError("Test refused")
        if method == "lovelace/dashboards/list":
            return [{"url_path": x} for x in self.existing]
        if method == "lovelace/config/save":
            self.saved = kw["config"]
            return None
        if method == "lovelace/config":
            return self.saved
        return {"id": "new"}


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []
        self.closed = False

    def recv(self):
        return json.dumps(next(self.messages))

    def send(self, text):
        self.sent.append(json.loads(text))

    def close(self):
        self.closed = True


class DashboardPublisherTests(unittest.TestCase):
    def test_websocket_uses_matching_message_ids(self):
        fake = FakeSocket([{"type": "auth_ok"},
                           {"id": 999, "type": "event"},
                           {"id": 1, "type": "result", "success": True, "result": []}])
        with HAWebSocket(fake) as client:
            self.assertEqual(client.call("lovelace/dashboards/list"), [])
        self.assertEqual(fake.sent[0], {"id": 1, "type": "lovelace/dashboards/list"})
        self.assertTrue(fake.closed)

    def test_creates_once_after_explicit_confirmation(self):
        fake = FakeClient()
        result = publish(PAYLOAD, LAYOUT, ENTITIES, client_factory=lambda: fake)
        self.assertTrue(result["created"])
        self.assertEqual([x[0] for x in fake.calls], [
            "lovelace/dashboards/list", "lovelace/dashboards/create",
            "lovelace/config/save", "lovelace/config"])

    def test_refuses_existing_dashboard_without_writing(self):
        fake = FakeClient(existing=["nm-studio-test"])
        with self.assertRaisesRegex(PublishError, "già esistente"):
            publish(PAYLOAD, LAYOUT, ENTITIES, client_factory=lambda: fake)
        self.assertEqual([x[0] for x in fake.calls], ["lovelace/dashboards/list"])

    def test_requires_confirmation(self):
        with self.assertRaisesRegex(PublishError, "Conferma"):
            publish({**PAYLOAD, "confirm": False}, LAYOUT, ENTITIES)

    def test_refuses_stale_preview(self):
        with self.assertRaisesRegex(PublishError, "Anteprima"):
            publish({**PAYLOAD, "expected_fingerprint": "stale"}, LAYOUT, ENTITIES)

    def test_rejects_arbitrary_dashboard_paths(self):
        for path in ("lovelace", "dashboard-cliente", "nm-studio-../x", "nm-studio-a"):
            with self.subTest(path=path), self.assertRaises(PublishError):
                publish({**PAYLOAD, "url_path": path}, LAYOUT, ENTITIES)

    def test_save_failure_does_not_delete_or_overwrite(self):
        fake = FakeClient(fail="lovelace/config/save")
        with self.assertRaisesRegex(PublishError, "Dashboard creata"):
            publish(PAYLOAD, LAYOUT, ENTITIES, client_factory=lambda: fake)
        self.assertNotIn("lovelace/dashboards/delete", [x[0] for x in fake.calls])

    def test_zero_operational_cards_never_create_dashboard(self):
        missing = {**LAYOUT, "widgets": [{**LAYOUT["widgets"][0], "entity_id": ""}]}
        payload = {**PAYLOAD, "expected_fingerprint": generate(missing, ENTITIES)["fingerprint"]}
        fake = FakeClient()
        with self.assertRaisesRegex(PublishError, "Nessuna entità"):
            publish(payload, missing, ENTITIES, client_factory=lambda: fake)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()



class DashboardUpdateTests(unittest.TestCase):
    def setup_update(self):
        from nm_bridge.dashboard_publisher import preview_update
        generated = generate(LAYOUT, ENTITIES)
        fake = FakeClient(existing=[generated['url_path']])
        fake.saved = {'title': 'Nome cliente', 'views': [{'title': 'Personalizzata', 'cards': []}]}
        request = {'url_path': generated['url_path']}
        preview = preview_update(request, LAYOUT, ENTITIES, lambda: fake)
        return fake, {**request, 'confirm': True, 'expected_current': preview['expected_current'],
                      'expected_fingerprint': preview['expected_fingerprint']}

    def test_preview_does_not_write_and_backup_precedes_save(self):
        import tempfile
        from pathlib import Path
        from nm_bridge.dashboard_publisher import update_existing
        fake, payload = self.setup_update()
        before = json.loads(json.dumps(fake.saved))
        self.assertNotIn('lovelace/config/save', [c[0] for c in fake.calls])
        with tempfile.TemporaryDirectory() as directory:
            original_call = fake.call
            def checked(method, **kw):
                if method == 'lovelace/config/save':
                    files = list(Path(directory).glob('*.json'))
                    self.assertEqual(len(files), 1)
                    self.assertEqual(json.loads(files[0].read_text(encoding='utf-8'))['config'], before)
                return original_call(method, **kw)
            fake.call = checked
            result = update_existing(payload, LAYOUT, ENTITIES, lambda: fake, directory)
            self.assertTrue(result['updated'])
            self.assertEqual(fake.saved['title'], 'Nome cliente')
            self.assertEqual(result['previous_dashboard'], before)
            self.assertTrue((Path(directory)/result['backup']).is_file())

    def test_changed_dashboard_or_source_cannot_overwrite(self):
        import tempfile
        from nm_bridge.dashboard_publisher import update_existing
        for change in ['dashboard', 'source', 'confirmation', 'path']:
            fake, payload = self.setup_update()
            if change == 'dashboard': fake.saved['views'].append({'title': 'Nuova'})
            if change == 'source': payload['expected_fingerprint'] = 'old'
            if change == 'confirmation': payload['confirm'] = False
            if change == 'path': payload['url_path'] = 'nm-studio-other-project'
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(PublishError):
                update_existing(payload, LAYOUT, ENTITIES, lambda: fake, directory)
            self.assertNotIn('lovelace/config/save', [c[0] for c in fake.calls])

    def test_backup_failure_prevents_ha_write(self):
        import tempfile
        from pathlib import Path
        from nm_bridge.dashboard_publisher import update_existing
        fake, payload = self.setup_update()
        with tempfile.TemporaryDirectory() as directory:
            blocked = Path(directory)/'file'; blocked.write_text('existing')
            with self.assertRaises(OSError):
                update_existing(payload, LAYOUT, ENTITIES, lambda: fake, blocked)
        self.assertNotIn('lovelace/config/save', [c[0] for c in fake.calls])

    def test_write_failure_preserves_backup_and_does_not_delete(self):
        import tempfile
        from pathlib import Path
        from nm_bridge.dashboard_publisher import update_existing
        fake, payload = self.setup_update(); fake.fail = 'lovelace/config/save'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(PublishError, 'Backup disponibile'):
                update_existing(payload, LAYOUT, ENTITIES, lambda: fake, directory)
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 1)
        self.assertNotIn('lovelace/dashboards/delete', [c[0] for c in fake.calls])

    def test_change_during_backup_prevents_write(self):
        import tempfile
        from nm_bridge.dashboard_publisher import update_existing
        fake, payload = self.setup_update(); original_call = fake.call; reads = 0
        def changed(method, **kw):
            nonlocal reads
            value = original_call(method, **kw)
            if method == 'lovelace/config':
                reads += 1
                if reads == 2: return {'views': [{'title': 'Concurrent edit'}]}
            return value
        fake.call = changed
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(PublishError, 'durante il backup'):
            update_existing(payload, LAYOUT, ENTITIES, lambda: fake, directory)
        self.assertNotIn('lovelace/config/save', [c[0] for c in fake.calls])
