import copy
import unittest
import xml.etree.ElementTree as ET

from nm_bridge.ets_object_functions import object_dimmers, enrich_suggestions
from nm_bridge.ets_import import application_file, instance_details


def circuit(module=1, offset=0):
    items = []
    for i, (dpt, size, write) in enumerate([
        ('DPST-1-1', '1 Bit', True), ('DPST-3-7', '4 Bit', True),
        ('DPST-5-1', '1 Byte', True), ('DPST-1-1', '1 Bit', False),
        ('DPST-5-1', '1 Byte', False)]):
        items.append(dict(address=f'1/1/{offset+i}', name=f'Arbitrary {offset+i}',
                          dpt=dpt, linked=True, connections=[dict(device_id='dev',
                          object_ref=f'MD-1_M-1_MI-{module}_O-{i}_R-1', dpt=dpt,
                          size=size, flags=dict(CommunicationFlag=True,
                                              WriteFlag=write, TransmitFlag=not write))]))
    return items


class ObjectImportTests(unittest.TestCase):
    def test_names_are_irrelevant_and_channels_stay_separate(self):
        items = circuit() + circuit(2, 10)
        result = object_dimmers(items)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['brightness_feedback'], '1/1/4')
        self.assertEqual(result[1]['brightness'], '1/1/12')
        for item in items:
            item['name'] = ''
        self.assertEqual([s['command'] for s in object_dimmers(items)], ['1/1/0', '1/1/10'])

    def test_missing_evidence_and_conflicts_do_not_infer(self):
        for change in ('scope', 'dpt', 'size', 'direction', 'unlinked', 'disabled'):
            with self.subTest(change=change):
                items = circuit()
                obj = items[1]['connections'][0]
                if change == 'scope': obj['object_ref'] = 'O-1_R-1'
                if change == 'dpt': obj['dpt'] = 'DPST-3-8'
                if change == 'size': obj['size'] = '1 Byte'
                if change == 'direction': obj['flags'].pop('TransmitFlag')
                if change == 'unlinked': items[1]['linked'] = False
                if change == 'disabled': obj['flags']['CommunicationFlag'] = False
                self.assertFalse(object_dimmers(items))

    def test_percent_alone_is_not_a_dimmer(self):
        self.assertFalse(object_dimmers([a for a in circuit() if a['dpt'] != 'DPST-3-7']))

    def test_multifunction_module_is_not_assumed_to_be_one_channel(self):
        items = circuit()
        extra = copy.deepcopy(items[0])
        extra['address'] = '1/1/99'
        extra['dpt'] = extra['connections'][0]['dpt'] = 'DPST-1-8'
        items.append(extra)
        self.assertFalse(object_dimmers(items))

    def test_duplicate_links_and_ambiguous_roles(self):
        items = circuit()
        items[2]['connections'] *= 2
        self.assertEqual(object_dimmers(items)[0]['brightness'], '1/1/2')
        duplicate = copy.deepcopy(items[2])
        duplicate['address'] = '1/1/90'
        items.append(duplicate)
        result = object_dimmers(items)[0]
        self.assertNotIn('brightness', result)
        self.assertEqual(result['confidence'], 'bassa')

    def test_broadcast_scopes_must_agree(self):
        items = circuit() + circuit(2, 10)
        items[5]['address'] = items[0]['address']
        self.assertFalse(object_dimmers(items))  # Same command, different relative GA.

    def test_enrichment_keeps_conflicting_prior_mapping_visible(self):
        prior = dict(command='1/1/0', kind='dimmer', brightness='1/1/99', reason='', confidence='media')
        result = enrich_suggestions(circuit(), [prior])[0]
        self.assertEqual(result['brightness'], '1/1/99')
        self.assertEqual(result['relative'], '1/1/1')
        self.assertEqual(result['confidence'], 'bassa')
        self.assertNotIn('relative', prior)

    def test_catalog_suffix_and_project_overrides(self):
        node = ET.Element('DeviceInstance', Hardware2ProgramRefId='M-0001_H-12_HP-1234-01-ABCD-O00EF')
        self.assertEqual(application_file(node), 'M-0001/M-0001_A-1234-01-ABCD-O00EF.xml')
        node.set('Hardware2ProgramRefId', 'M-0001_HP-../../bad')
        self.assertIsNone(application_file(node))
        base = dict(flags=dict(WriteFlag=True, TransmitFlag=False))
        obj = ET.Element('ComObjectInstanceRef', WriteFlag='Disabled', TransmitFlag='Default')
        self.assertEqual(instance_details(base, obj)['flags'], dict(WriteFlag=False, TransmitFlag=False))
        self.assertTrue(base['flags']['WriteFlag'])
