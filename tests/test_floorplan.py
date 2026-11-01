import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nm_bridge import floorplan


PNG = 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'fake-png').decode()


class FloorplanTests(unittest.TestCase):
    def test_roundtrip_with_layer_points(self):
        data = {"version": 1, "plans": [{"id": "floor_1", "name": "Piano terra", "background": PNG,
                 "points": [{"id": "D01", "kind": "data", "label": "Presa D01", "x": 12.3456, "y": 77.55},
                            {"id": "L01", "kind": "dali", "label": "ECG 12", "x": 50, "y": 40}]}]}
        with tempfile.TemporaryDirectory() as folder, patch.object(floorplan, "PATH", Path(folder) / "plans.json"):
            result = floorplan.save(data)
            self.assertEqual(result["points"], 2)
            saved = floorplan.read()
            self.assertEqual(saved["plans"][0]["points"][0]["x"], 12.346)
            self.assertEqual(saved["plans"][0]["background"], PNG)

    def test_rejects_invalid_images_and_coordinates(self):
        doc = {"version": 1, "plans": [{"id": "floor", "name": "Floor", "background": "data:text/html;base64,abc", "points": []}]}
        with self.assertRaises(ValueError):
            floorplan.validate(doc)
        doc["plans"][0]["background"] = None
        doc["plans"][0]["points"] = [{"id": "p1", "kind": "light", "label": "Luce", "x": 150, "y": 2}]
        with self.assertRaises(ValueError):
            floorplan.validate(doc)

    def test_rejects_duplicate_ids_and_unexpected_kinds(self):
        point = {"id": "p1", "kind": "light", "label": "Luce", "x": 50, "y": 50}
        doc = {"version": 1, "plans": [{"id": "floor", "name": "Floor", "points": [point, point]}]}
        with self.assertRaises(ValueError):
            floorplan.validate(doc)
        doc["plans"][0]["points"] = [{**point, "kind": ["unsafe"]}]
        with self.assertRaises(ValueError):
            floorplan.validate(doc)
