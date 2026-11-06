import unittest
from nm_bridge.ets_named_functions import descriptive_suggestions
from nm_bridge.widget_layout import validate_structure
from nm_bridge.knx_entity_plan import build
from nm_bridge.missing_ha_generator import fingerprint


def address(name, dpt, number, linked=True):
    return dict(name=name, dpt=dpt, address=f'3/1/{number}', linked=linked)


class DescriptiveImportTests(unittest.TestCase):
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
