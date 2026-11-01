"""Recorder fallback is bounded and never makes a service call."""

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nm_bridge"))
import bridge  # noqa: E402


class Response:
    def __init__(self, contents):
        self.contents = contents

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.contents[:size]


class RecorderTests(unittest.TestCase):
    def test_fallback_from_24_hours_to_6(self):
        now = datetime.now(timezone.utc)
        state = {"entity_id": "sensor.sim", "attributes": {
            "decision_id": "test", "simulation": True, "actions": [],
            "status": "nessuna_azione", "generated_at": now.isoformat(),
            "summary": "Test"}}
        calls = []

        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                return Response(b"x" * (2 * 1024 * 1024 + 1))
            return Response(json.dumps([[state]]).encode())

        with patch.object(bridge, "get_ha_states", return_value=[state]), \
             patch.object(bridge, "urlopen", side_effect=fake_urlopen), \
             patch.dict(bridge.os.environ, {"SUPERVISOR_TOKEN": "test"}):
            result = bridge.get_decision_history()
        self.assertEqual(result["hours"], 6)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("filter_entity_id=sensor.sim" in url for url in calls))


if __name__ == "__main__":
    unittest.main()
