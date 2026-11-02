import io
import unittest
import zipfile
from xml.sax.saxutils import escape

from nm_bridge.ets_import import preview


def archive_with_addresses(entries, linked=()):
    content = '<Project><GroupAddresses>' + ''.join(
        '<GroupAddress Id="P-0001-0_GA-{}" Address="{}" Name="{}" />'.format(i, addr, escape(name, {'"': '&quot;'}))
        for i, (addr, name) in enumerate(entries)
    ) + '</GroupAddresses><DeviceInstance Description="Test"><ComObjectInstanceRefs>' + ''.join(
        '<ComObjectInstanceRef RefId="O-{}" Links="GA-{}" />'.format(i, i) for i in linked
    ) + '</ComObjectInstanceRefs></DeviceInstance></Project>'
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('P-0001/0.xml', content)
    return data.getvalue()


class ETSImportTests(unittest.TestCase):
    def test_physical_device_links_have_stable_local_identifier(self):
        result = preview(archive_with_addresses([(0x0900, 'ON/OFF L1')], linked=(0,)))
        device = result['devices'][0]
        connection = result['addresses'][0]['connections'][0]
        self.assertEqual(device['id'], connection['device_id'])
        self.assertEqual(device['connected_objects'], 1)
        self.assertEqual(device['linked_addresses'], 1)

    def test_instantiated_object_without_links_is_reported_separately(self):
        project = ('<Project><GroupAddress Id="P-0001-0_GA-1" Address="2304" Name="MOVIMENTO T1" />'
                   '<DeviceInstance Description="Attuatore"><ComObjectInstanceRef RefId="O-1" Links="GA-1" />'
                   '<ComObjectInstanceRef RefId="O-2" /></DeviceInstance></Project>')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('P-0001/0.xml', project)
        result = preview(data.getvalue())
        device = result['devices'][0]
        self.assertEqual(device['connected_objects'], 1)
        self.assertEqual(device['unlinked_count'], 1)
        self.assertEqual(device['unlinked_objects'][0]['object_ref'], 'O-2')

    def test_application_reference_overrides_generic_object(self):
        project = ('<Project><GroupAddress Id="P-0001-0_GA-1" Address="2304" Name="ON/OFF L1" />'
                   '<DeviceInstance Description="Ingresso" Hardware2ProgramRefId="M-0019_H-X_HP-1234-11-ABCD">'
                   '<ComObjectInstanceRef RefId="O-1_R-9" Links="GA-1" /></DeviceInstance></Project>')
        catalog = ('<Application><ComObject Id="M-0019_A-1234-11-ABCD_O-1" Name="Commutazione" ObjectSize="4 Bytes" />'
                   '<ComObjectRef Id="M-0019_A-1234-11-ABCD_O-1_R-9" RefId="M-0019_A-1234-11-ABCD_O-1" '
                   'Text="Movimento tapparelle" FunctionText="Su/Giù" ObjectSize="1 Bit" /></Application>')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('P-0001/0.xml', project)
            z.writestr('M-0019/M-0019_A-1234-11-ABCD.xml', catalog)
        result = preview(data.getvalue())
        obj = result['addresses'][0]['connections'][0]
        self.assertEqual(obj['name'], 'Movimento tapparelle')
        self.assertEqual(obj['size'], '1 Bit')

    def test_catalog_object_not_instantiated_is_only_a_candidate(self):
        project = ('<Project><GroupAddress Id="P-0001-0_GA-1" Address="2304" Name="MOVIMENTO T1" />'
                   '<DeviceInstance Description="Attuatore" Hardware2ProgramRefId="M-0019_H-X_HP-1234-11-ABCD">'
                   '<ComObjectInstanceRef RefId="O-1_R-9" Links="GA-1" /></DeviceInstance></Project>')
        catalog = ('<Application><ComObject Id="M-0019_A-1234-11-ABCD_O-1" Name="Movimento" />'
                   '<ComObject Id="M-0019_A-1234-11-ABCD_O-2" Name="Comando posizione" /></Application>')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('P-0001/0.xml', project)
            z.writestr('M-0019/M-0019_A-1234-11-ABCD.xml', catalog)
        device = preview(data.getvalue())['devices'][0]
        self.assertEqual(device['unlinked_count'], 0)
        self.assertEqual(device['catalog_candidates_count'], 1)
        self.assertEqual(device['catalog_candidates'][0]['name'], 'Comando posizione')

    def test_light_and_dimmer_suggestions(self):
        data = archive_with_addresses([
            (0x0900, 'ON/OFF L1'), (0x0904, 'STATO L1'),
            (0x0801, 'DIMMER ON/OFF L11'),
            (0x0803, 'NOTIFICA STATO DIMMER ON/OFF L11'),
            (0x0908, 'STATO L2'),
        ])
        result = preview(data)
        suggestions = {x['name']: x for x in result['suggestions']}
        self.assertEqual(suggestions['L1']['kind'], 'light')
        self.assertEqual(suggestions['L1']['command'], '1/1/0')
        self.assertEqual(suggestions['L1']['confidence'], 'media')
        self.assertEqual(suggestions['DIMMER L11']['kind'], 'dimmer')
        self.assertEqual(suggestions['DIMMER L11']['feedback'], '1/0/3')
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(next(x for x in result['addresses'] if x['address'] == '1/1/0')['kind'], 'light')

    def test_ambiguous_feedback_is_not_suggested(self):
        result = preview(archive_with_addresses([
            (0x0900, 'ON/OFF L1'), (0x0904, 'STATO L1'), (0x0905, 'FEEDBACK L1')
        ]))
        self.assertEqual(result['suggestions'], [])

    def test_stato_led_numbered_light_pairs_with_command(self):
        result = preview(archive_with_addresses([
            (0x0908, 'ON/OFF L5'), (0x090B, 'STATO LED L5'),
            (0x0909, 'ON/OFF L6'), (0x090C, 'STATO LED L6'),
            (0x090A, 'ON/OFF L7'), (0x090D, 'STATO LED L7'),
        ], linked=(0, 1, 2, 3, 4, 5)))
        suggestions = {s['name']: s for s in result['suggestions']}
        self.assertEqual(set(suggestions), {'L5', 'L6', 'L7'})
        self.assertEqual(suggestions['L5']['command'], '1/1/8')
        self.assertEqual(suggestions['L5']['feedback'], '1/1/11')
        self.assertEqual(suggestions['L6']['feedback'], '1/1/12')
        self.assertEqual(suggestions['L7']['feedback'], '1/1/13')

    def test_generic_led_feedback_is_not_merged_with_other_light(self):
        result = preview(archive_with_addresses([
            (0x0900, 'ON/OFF BAGNO'), (0x0904, 'STATO LED BAGNO'),
        ]))
        self.assertEqual(result['suggestions'], [])

    def test_generic_binary_is_not_assumed_light(self):
        result = preview(archive_with_addresses([(0x0900, 'ON/OFF POMPA'), (0x0904, 'STATO POMPA')]))
        self.assertEqual(result['suggestions'][0]['kind'], 'unknown')

    def test_room_guess_is_conservative(self):
        result = preview(archive_with_addresses([
            (0x0900, 'ON/OFF LUCE UFFICIO'), (0x0904, 'STATO LUCE UFFICIO'),
            (0x0901, 'ON/OFF L2'), (0x0905, 'STATO L2'),
        ]))
        rooms = {s['name']: s['room'] for s in result['suggestions']}
        self.assertEqual(rooms['LUCE UFFICIO'], 'Ufficio')
        self.assertEqual(rooms['L2'], 'Da assegnare')

    def test_cover_with_multiple_addresses_is_proposed(self):
        result = preview(archive_with_addresses([
            (0x0A00, 'MOVIMENTO SU/GIU T1'), (0x0A01, 'ARRESTO T1'),
            (0x0A02, 'POSIZIONE T1'), (0x0A03, 'MOVIMENTO SU/GIU T2'),
        ], linked=(0, 1, 3)))
        covers = {s['name']: s for s in result['suggestions']}
        self.assertEqual(covers['T1']['kind'], 'cover')
        self.assertEqual(covers['T1']['command'], '1/2/0')
        self.assertEqual(covers['T1']['stop'], '1/2/1')
        self.assertIsNone(covers['T1']['position'])
        self.assertIn('NON è collegato', covers['T1']['reason'])
        self.assertIsNone(covers['T1']['feedback'])
        self.assertEqual(covers['T2']['confidence'], 'bassa')


if __name__ == '__main__':
    unittest.main()
