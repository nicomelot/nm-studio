import io
import unittest
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

from nm_bridge.ets_import import preview
from nm_bridge.lab_devices import candidates


def fixture():
    project = Element('Project')
    groups = SubElement(project, 'GroupAddresses')
    group_entries = [
        ('Clima sala ON/OFF', 'DPST-1-1'),
        ('Clima sala STATO', 'DPST-1-1'),
        ('SET POINT TEMPERATURA', 'DPST-9-1'),
        ("MODALITA'", 'DPST-20-105'),
        ("MODALITA' STATO", 'DPST-20-105'),
        ('SET POINT TEMPERATURA', 'DPST-9-1'),
        ("MODALITA'", 'DPST-20-102'),
        ('Luce corridoio ON/OFF L1', 'DPST-1-1'),
        ('Luce corridoio STATO L1', 'DPST-1-1'),
        ('VENT. A CONTROL ON/OFF', 'DPST-1-1'),
    ]
    for i, (name, dpt) in enumerate(group_entries):
        SubElement(groups, 'GroupAddress', Id=f'P-0001_GA-{i}', Address=str(2048+i), Name=name, DPTs=dpt)
    area = SubElement(project, 'Area', Address='1')
    line = SubElement(area, 'Line', Address='1')
    building = SubElement(SubElement(project, 'Locations'), 'Space', Type='Building', Name='Progetto')

    def add_device(suffix, product, room, addresses):
        ident = f'P-0001_DI-{suffix}'
        device = SubElement(line, 'DeviceInstance', Id=ident, Address=str(suffix), ProductRefId=product)
        for i in addresses:
            SubElement(device, 'ComObjectInstanceRef', RefId=f'O-{i}', Links=f'GA-{i}')
        space = SubElement(building, 'Space', Type='Room', Name=room)
        SubElement(space, 'DeviceInstanceRef', RefId=ident)

    product = 'M-0071_H-ZCLDIV2-1_P-ZCLDIV2'
    gateway = 'M-0077_H-DK.2DRC.2DKNX.2D1i-32_P-DK.2DRC.2DKNX.2D1i'
    add_device(51, product, 'Sala', [0, 1, 2, 3, 4])
    # More than twelve direct object links on the same GA. A display limit
    # must never hide the fact that the second unit shares a command.
    for i in range(100, 113):
        add_device(i, 'Other product', 'Tecnico', [3])
    add_device(52, product, 'Cucina', [3, 5, 6])
    add_device(53, product, 'Da allestire', [])
    add_device(54, 'Other product', 'Corridoio', [7, 8])
    add_device(70, gateway, 'Locale tecnico A', [9])
    add_device(71, gateway, 'Locale tecnico B', [9])
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('P-0001/0.xml', tostring(project))
    return output.getvalue()


class HVACDeviceImportTests(unittest.TestCase):
    def test_groups_generic_names_by_device_and_detects_shared_links(self):
        result = preview(fixture())
        units = {unit['individual_address']: unit for unit in result['hvac_units']}
        self.assertEqual(set(units), {'1.1.51', '1.1.52', '1.1.53', '1.1.70', '1.1.71'})
        sala, cucina = units['1.1.51'], units['1.1.52']
        self.assertEqual(sala['rooms'], ['Progetto / Sala'])
        self.assertEqual(cucina['rooms'], ['Progetto / Cucina'])
        self.assertIn('1/0/2', {point['address'] for point in sala['points']})
        self.assertNotIn('1/0/2', {point['address'] for point in cucina['points']})
        shared = next(point for point in sala['points'] if point['address'] == '1/0/3')
        self.assertEqual(shared['label'], 'Modalità clima')
        self.assertEqual(shared['direction'], 'command')
        self.assertTrue(shared['shared_hvac'])
        self.assertEqual(shared['peer_count'], 14)
        self.assertEqual(shared['shared_with'][0]['individual_address'], '1.1.52')
        self.assertEqual(units['1.1.53']['points'], [])
        self.assertTrue(units['1.1.70']['points'][0]['shared_hvac'])

    def test_preserves_non_hvac_drafts_and_leaves_incompatible_dpt_unclassified(self):
        result = preview(fixture())
        cucina = next(unit for unit in result['hvac_units'] if unit['individual_address'] == '1.1.52')
        incompatible = next(point for point in cucina['points'] if point['address'] == '1/0/6')
        self.assertEqual(incompatible['direction'], 'unknown')
        self.assertEqual({proposal['command'] for proposal in result['suggestions']}, {'1/0/7'})
        self.assertEqual({candidate['command'] for candidate in candidates(result)}, {'1/0/7'})
