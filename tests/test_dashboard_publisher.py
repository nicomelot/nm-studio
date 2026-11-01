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
