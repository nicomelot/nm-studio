import unittest
from pathlib import Path

from nm_bridge.knx_yaml_audit import inspect_yaml


class KnxYamlAuditTests(unittest.TestCase):
    def test_duplicates_and_probable_feedback(self):
        result = inspect_yaml('''light:
  - name: "PULSANTIERA L1"
    address: '1/1/0'
    state_address: '1/1/4'
  - name: "SCATOLA L1"
    address: '1/1/0'
  - name: "NOTIFICA STATO L11"
    address: '1/0/3'
cover:
  - name: "T1"
    move_long_address: '1/2/0'
    stop_address: '1/2/1'
''')
        self.assertEqual(result['counts'], {'light': 3, 'cover': 1, 'duplicate_groups': 1,
                                            'extra_entities': 1, 'feedback_candidates': 1})
        group = next(g for g in result['groups'] if g['command'] == '1/1/0')
        self.assertEqual(group['feedback'], ['1/1/4'])
        self.assertTrue(result['read_only'])

    def test_no_entries_or_tags(self):
        with self.assertRaises(ValueError):
            inspect_yaml('knx: !include knx_imported.yaml')
        with self.assertRaises(ValueError):
            inspect_yaml('light:\n  - name: !secret my_secret\n    address: 1/1/0')

    def test_real_file_if_available(self):
        path = Path(__file__).resolve().parents[2] / 'upload' / 'knx_imported.yaml'
        if not path.exists():
            self.skipTest('File utente non distribuito nel repository')
        result = inspect_yaml(path.read_text())
        self.assertEqual(result['counts']['light'], 37)
        self.assertEqual(result['counts']['cover'], 2)
        self.assertEqual(result['counts']['duplicate_groups'], 8)
        self.assertEqual(result['counts']['feedback_candidates'], 1)


if __name__ == '__main__':
    unittest.main()
