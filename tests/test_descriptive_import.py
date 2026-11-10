import unittest
from nm_bridge.ets_named_functions import descriptive_suggestions
from nm_bridge.widget_layout import validate_structure
from nm_bridge.knx_entity_plan import build
from nm_bridge.missing_ha_generator import fingerprint
from nm_bridge.ets_import import catalog_key, catalog_objects
import io
import zipfile


def address(name, dpt, number, linked=True):
    return dict(name=name, dpt=dpt, address=f'3/1/{number}', linked=linked)


class DescriptiveImportTests(unittest.TestCase):
    def test_short_shutter_roles_and_direction_state(self):
        items = [address('SERRANDA UFFICIO ' + role, dpt, i) for i, (role, dpt) in enumerate([
            ('SU/GIU', 'DPST-1-8'), ('STOP', 'DPST-1-17'),
            ('SU/GIU STATO', 'DPST-1-8'), ('POSIZIONE', 'DPST-5-1'),
            ('POSIZIONE STATO', 'DPST-5-1')])]
        result = descriptive_suggestions(items)[0][0]
        self.assertEqual(result['stop'], '3/1/1')
        self.assertEqual(result['position_command'], '3/1/3')
        self.assertEqual(result['position_feedback'], '3/1/4')
        self.assertNotIn('feedback', result)
        self.assertEqual(result['confidence'], 'media')
        items.append(address('SERRANDA UFFICIO STOP', 'DPST-1-17', 10))
        self.assertNotIn('stop', descriptive_suggestions(items)[0][0])

    def test_collective_cover_does_not_claim_aggregate_position(self):
        items = [address('TAPPARELLE TUTTE ' + role, dpt, i) for i, (role, dpt) in enumerate([
            ('SU/GIU', 'DPST-1-8'), ('STOP', 'DPST-1-17'),
            ('POSIZIONE', 'DPST-5-1'), ('POSIZIONE STATO', 'DPST-5-1')])]
        result = descriptive_suggestions(items)[0][0]
        self.assertTrue(result['collective'])
        self.assertEqual(result['position_command'], '3/1/2')
        self.assertNotIn('position_feedback', result)
        self.assertIn('stato collettivo da verificare', result['reason'])

    def test_general_switch_requires_receiver_and_preserves_off_only(self):
        item = address('OFF GENERALE', 'DPST-1-1', 0)
        self.assertFalse(descriptive_suggestions([item])[0])
        obj = dict(function='On/Off', dpt='DPST-1-1',
                   flags=dict(WriteFlag=True, TransmitFlag=False, CommunicationFlag=True))
        item['connections'] = [obj]
        result = descriptive_suggestions([item])[0][0]
        self.assertEqual(result['command_mode'], 'off_only')
        self.assertTrue(result['collective'])
        self.assertNotIn('feedback', result)
        for name in ('ON/OFF GENERALE', 'GENERALE LUCI ON/OFF'):
            item['name'] = name
            self.assertEqual(descriptive_suggestions([item])[0][0]['command_mode'], 'toggle')
        for name in ('CAMPANELLO ON', 'APRI PORTA ON', 'ON GENERALE'):
            item['name'] = name
            self.assertFalse(descriptive_suggestions([item])[0])
        item['name'] = 'OFF GENERALE'
        obj['flags']['WriteFlag'] = False
        self.assertFalse(descriptive_suggestions([item])[0])
        obj['flags']['WriteFlag'] = True
        item['dpt'] = 'DPST-1-8'
        self.assertFalse(descriptive_suggestions([item])[0])

    def test_short_dimmer_names_and_repeated_switch_suffix(self):
        for prefix in ('Sala', 'Sala ON/OFF'):
            with self.subTest(prefix=prefix):
                items = [address('Sala ON/OFF', 'DPST-1-1', 0)] + [
                    address(prefix + ' ' + role, dpt, i + 1)
                    for i, (role, dpt) in enumerate([
                        ('DIMMER', 'DPST-3-7'), ('VALORE', 'DPST-5-1'),
                        ('STATO', 'DPST-1-1'), ('VALORE STATO', 'DPST-5-1')])]
                result, consumed = descriptive_suggestions(items)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['kind'], 'dimmer')
                self.assertEqual(result[0]['brightness'], '3/1/2')
                self.assertEqual(result[0]['feedback'], '3/1/3')
                self.assertEqual(result[0]['brightness_feedback'], '3/1/4')
                self.assertEqual(len(consumed), 5)

    def test_short_state_uses_dpt_and_alias_conflicts_remain_unresolved(self):
        items = [address('Sala ' + role, dpt, i) for i, (role, dpt) in enumerate([
            ('ON/OFF', 'DPST-1-1'), ('DIMMER', 'DPST-3-7'),
            ('VALORE', 'DPST-5-1'), ('STATO', 'DPST-1-1'),
            ('STATO', 'DPST-5-1')])]
        result = descriptive_suggestions(items)[0][0]
        self.assertEqual(result['feedback'], '3/1/3')
        self.assertEqual(result['brightness_feedback'], '3/1/4')
        items.append(address('Sala DIMMING ASSOLUTO', 'DPST-5-1', 30))
        result = descriptive_suggestions(items)[0][0]
        self.assertNotIn('brightness', result)
        self.assertEqual(result['confidence'], 'bassa')

    def test_short_names_require_linked_compatible_roles(self):
        for dpt, linked in [('DPST-9-1', True), ('DPST-5-1', False)]:
            self.assertFalse(descriptive_suggestions([
                address('Sala ON/OFF', 'DPST-1-1', 0),
                address('Sala VALORE', dpt, 1, linked)])[0])
        items = [address('Gruppo 1 ON/OFF', 'DPST-1-1', 0),
                 address('Gruppo 2 VALORE', 'DPST-5-1', 1)]
        self.assertFalse(descriptive_suggestions(items)[0])

    def test_module_catalog_keeps_namespaces_and_reference_overrides(self):
        data = io.BytesIO()
        xml = '''<Root><ComObject Id="APP_MD-1_O-2-32" ObjectSize="1 Bit" FunctionText="Switch" WriteFlag="Enabled" DatapointType="DPST-1-1"/>
        <ComObject Id="APP_MD-2_O-2-32" ObjectSize="1 Bit" FunctionText="Stop" WriteFlag="Enabled" DatapointType="DPST-1-7"/>
        <ComObjectRef Id="APP_MD-2_O-2-32_R-2" RefId="APP_MD-2_O-2-32" FunctionText="Short term operation/Stop" DatapointType="DPST-1-8"/>
        <ComObject Id="APP_MD-3_O-2-32" ObjectSize="1 Bit" FunctionText="Alarm" WriteFlag="Disabled" DatapointType="DPST-1-5"/></Root>'''
        with zipfile.ZipFile(data, 'w') as z:
            z.writestr('app.xml', xml)
        with zipfile.ZipFile(data) as z:
            catalog = catalog_objects(z, 'app.xml', {}, [0])
        key = catalog_key('MD-2_M-62_MI-1_O-2-32_R-2')
        self.assertEqual(key, 'MD-2_O-2-32_R-2')
        self.assertEqual(catalog[key]['dpt'], 'DPST-1-8')
        stop = address('TAPPARELLA SALA OPERAZIONE BREVE/STOP', 'DPST-1-8', 1)
        stop['connections'] = [catalog[key]]
        items = [address("TAPPARELLA SALA SU/GIU'", 'DPST-1-8', 0), stop]
        self.assertEqual(descriptive_suggestions(items)[0][0]['stop'], '3/1/1')
        stop['connections'] = [catalog['MD-3_O-2-32']]
        self.assertNotIn('stop', descriptive_suggestions(items)[0][0])

    def test_dimmer_roles_without_numbered_names(self):
        items = [address('Sala punti luce ' + role, dpt, i) for i, (role, dpt) in enumerate([
            ('ON/OFF', 'DPST-1-1'), ('DIMMING RELATIVO', 'DPST-3-7'),
            ('DIMMING ASSOLUTO', 'DPST-5-1'), ('STATO ON/OFF', 'DPST-1-1'),
            ('STATO VALORE', 'DPST-5-1')])]
        proposal = descriptive_suggestions(items)[0][0]
        self.assertEqual(proposal['kind'], 'dimmer')
        self.assertEqual(proposal['brightness'], '3/1/2')
        self.assertEqual(proposal['brightness_feedback'], '3/1/4')
        # Ambiguous roles must not be picked by iteration order.
        items.append(address('Sala punti luce DIMMING ASSOLUTO', 'DPST-5-1', 30))
        self.assertNotIn('brightness', descriptive_suggestions(items)[0][0])

    def test_unlinked_blocks_and_invalid_dpt_not_promoted(self):
        self.assertFalse(descriptive_suggestions([
            address('Sala ON/OFF', 'DPST-1-1', 0, False),
            address('Sala DIMMING ASSOLUTO', 'DPST-5-1', 1, False)])[0])
        self.assertFalse(descriptive_suggestions([
            address('Sala ON/OFF', 'DPST-1-1', 0),
            address('Sala DIMMING ASSOLUTO', 'DPST-9-1', 1)])[0])

    def test_cover_position_directions_and_mismatched_stop(self):
        result = descriptive_suggestions([
            address("TAPPARELLA SALA SU/GIU'", 'DPST-1-8', 0),
            address('TAPPARELLA SALA OPERAZIONE BREVE/STOP', 'DPST-1-8', 1),
            address('TAPPARELLA SALA POSIZIONE ASSOLUTA', 'DPST-5-1', 2),
            address('TAPPARELLA SALA SATO POSIZIONE ATTUALE', 'DPST-5-1', 3),
        ])[0][0]
        self.assertEqual(result['kind'], 'cover')
        self.assertNotIn('stop', result)
        self.assertIn('stop: GA ambiguo o DPT non compatibile', result['reason'])
        self.assertEqual(result['position_command'], '3/1/2')
        self.assertEqual(result['position_feedback'], '3/1/3')

    def test_room_without_floor_preserved(self):
        nodes = [dict(id='b', parent=None, type='building', name='Casa'),
                 dict(id='r', parent='b', type='room', name='Sala')]
        self.assertEqual(len(validate_structure(nodes)), 2)
        with self.assertRaises(ValueError):
            validate_structure(nodes + [dict(id='r2', parent='r', type='room', name='Altro')])

    def test_only_explicit_cover_position_fields_reach_ha(self):
        fields = dict(command='3/1/0', stop='3/1/1', position='3/1/90', feedback='3/1/91',
                      position_command='3/1/2', position_feedback='3/1/3')
        layout = dict(version=1, project='a'*64, widgets=[dict(type='cover', name='Tenda', fields=fields)])
        request = dict(source_fingerprint=fingerprint(layout), devices=[
            dict(index=0, approved=True, name='Tenda', fields=fields)])
        knx = build(layout, request)['calls'][0]['data']['knx']
        self.assertEqual(knx['ga_position_set'], {'write': '3/1/2'})
        self.assertEqual(knx['ga_position_state'], {'state': '3/1/3'})
        self.assertNotIn('3/1/90', str(knx))
        self.assertNotIn('3/1/91', str(knx))
