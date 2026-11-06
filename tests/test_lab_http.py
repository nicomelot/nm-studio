"""Exercise real ingress handler dispatch without opening ports or contacting HA."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nm_bridge"))
import bridge
from test_lab_devices import project, inventory
from lab_virtual import inspect as inspect_lab


def request(path, payload, address=None):
    handler = object.__new__(bridge.Handler)
    handler.path = path
    handler.client_address = (address or bridge.INGRESS_PROXY, 1234)
    raw = json.dumps(payload).encode()
    handler.headers = {"Content-Type": "application/json", "Content-Length": str(len(raw)), "Sec-Fetch-Site": "same-origin"}
    handler.rfile = io.BytesIO(raw)
    result = {}
    handler.respond = lambda status, content_type, body: result.update(status=status, data=json.loads(body))
    handler.send_error = lambda status: result.update(status=status)
    handler.do_POST()
    return result


class LabHTTPTests(unittest.TestCase):
    def test_protected_ets_upload_routes_password_without_retaining_it(self):
        handler = object.__new__(bridge.Handler)
        handler.path = "/ets/preview"
        handler.client_address = (bridge.INGRESS_PROXY, 1234)
        password = "test-password"
        encoded = password.encode()
        raw = len(encoded).to_bytes(4, "big") + encoded + b"PKxx"
        handler.headers = {"Content-Type": "application/vnd.nm.ets-upload", "Content-Length": str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        result = {}
        handler.respond = lambda status, content_type, body: result.update(status=status, data=json.loads(body))
        handler.send_error = lambda status: result.update(status=status)
        with patch.object(bridge, "ets_preview", return_value={"project_key": "synthetic"}) as importer, \
             patch.object(bridge, "lab_candidates", return_value=[]), \
             patch.object(bridge.PROJECTS, "prepare", side_effect=lambda data: data):
            handler.do_POST()
        importer.assert_called_once_with(b"PKxx", password=password)
        self.assertEqual(result["status"], 200)
        self.assertNotIn(password, json.dumps(result))

    def test_preview_and_dashboard_do_not_use_knx_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "configuration.yaml").write_text("homeassistant:\n  packages: !include_dir_named packages\n")
            with patch.object(bridge, "inspect_virtual_lab", side_effect=lambda data: inspect_lab(data, root)):
                response = request("/lab/preview", project())
            self.assertEqual(response["status"], 200)
            self.assertEqual(response["data"]["devices"], 6)
            with patch.object(bridge, "get_ha_states", return_value=inventory(project())):
                response = request("/lab/dashboard-preview", project())
            self.assertEqual(response["status"], 200)
            self.assertEqual(response["data"]["summary"]["tiles"], 6)

    def test_ingress_and_confirmation_are_enforced(self):
        self.assertEqual(request("/lab/install", project(), "127.0.0.1")["status"], 403)
        self.assertEqual(request("/lab/install", project())["status"], 400)
        self.assertEqual(request("/lab/replace", project())["status"], 400)
