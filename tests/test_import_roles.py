import unittest
from nm_bridge.ets_import import structured_suggestions


class ImportRolesTests(unittest.TestCase):
    def recognize(self, roles):
        items = [{'name': 'Locale - Circuito - ' + role, 'dpt': dpt,
                  'address': f'1/1/{i}', 'linked': True} for i, (role, dpt) in enumerate(roles)]
        return structured_suggestions(items)[0]

    def test_dimmer_does_not_require_optional_feedback(self):
        result = self.recognize([('ON/OFF comando', 'DPST-1-1'), ('Luminosità comando', 'DPST-5-1')])
        self.assertEqual(result[0]['kind'], 'dimmer')
        self.assertEqual(result[0]['brightness'], '1/1/1')
        self.assertNotIn('brightness_feedback', result[0])

    def test_relative_only_dimmer_stays_a_dimmer_for_review(self):
        result = self.recognize([('ON/OFF', '1.001'), ('Dimmer relativo', '3.007')])
        self.assertEqual(result[0]['kind'], 'dimmer')
        self.assertNotIn('brightness', result[0])

    def test_cover_without_numbered_t_name(self):
        result = self.recognize([('Salita/Discesa', 'DPST-1-8'), ('Arresto', 'DPST-1-7')])
        self.assertEqual(result[0]['kind'], 'cover')
        self.assertEqual(result[0]['stop'], '1/1/1')

    def test_cover_position_command_and_feedback_are_independent(self):
        movement = [('Movimento Comando', '1.008'), ('STOP', '1.017')]
        command = ('Posizione Comando', '5.001')
        feedback = ('Posizione Feedback', '5.001')
        for roles, expected in [
            ([command, feedback], {'position_command': '1/1/2', 'position_feedback': '1/1/3'}),
            ([command], {'position_command': '1/1/2'}),
            ([feedback], {'position_feedback': '1/1/2'}),
            ([('Posizione Feedback', '1.008')], {}),
        ]:
            with self.subTest(roles=roles):
                result = self.recognize(movement + roles)[0]
                self.assertEqual({k: v for k, v in result.items() if k.startswith('position')}, expected)

    def test_ambiguous_or_wrong_dpt_movement_never_assumed(self):
        self.assertFalse(self.recognize([('Su/Giù', '1.001'), ('Arresto', '1.007')]))
        self.assertFalse(self.recognize([('Su/Giù', '1.008'), ('Movimento', '1.008'), ('Arresto', '1.007')]))

    def test_two_part_names_remain_distinct_and_do_not_invent_room(self):
        items = [{'name': 'Tenda finestra - '+role, 'dpt': dpt, 'address': f'2/1/{i}', 'linked': True}
                 for i, (role, dpt) in enumerate([('Su/Giù', '1.008'), ('Stop', '1.007')])]
        result = structured_suggestions(items)[0][0]
        self.assertEqual(result['name'], 'Tenda finestra')
        self.assertEqual(result['room'], 'Da assegnare')
