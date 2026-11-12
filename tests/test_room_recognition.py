import unittest
from nm_bridge.ets_rooms import room_matches
from nm_bridge.lab_devices import candidates


class RoomRecognitionTests(unittest.TestCase):
    def match(self, name, paths, functions=None):
        return room_matches([{'command': '1/1/0', 'name': name}], [],
                            [{'path': p, 'type': 'Room'} for p in paths], functions or [])[0]

    def test_floor_suffix_and_common_abbreviation(self):
        paths = ['Casa / PIANO INTERRATO / Bagno PIANO INTERR.']
        self.assertEqual(self.match('Luce bagno', paths)['room'], paths[0])

    def test_duplicate_bathrooms_require_floor_evidence(self):
        paths = ['Casa / PIANO TERRA / Bagno', 'Casa / PIANO PRIMO / Bagno']
        self.assertEqual(self.match('Luce bagno', paths)['confidence'], 'ambiguous')
        self.assertEqual(self.match('Luce bagno primo', paths)['room'], paths[1])

    def test_specific_name_and_prepositions(self):
        paths = ['Casa / Terra / Bagno', 'Casa / Terra / Bagno ospiti']
        self.assertEqual(self.match('Luce bagno ospiti', paths)['room'], paths[1])
        paths = ['Casa / Primo / Camera da letto nord', 'Casa / Primo / Camera da letto sud']
        self.assertEqual(self.match('Luce camera letto nord', paths)['room'], paths[0])

    def test_explicit_function_wins_and_conflicts_remain_ambiguous(self):
        paths = ['Casa / Terra / Cucina', 'Casa / Terra / Bagno']
        functions = [{'space': paths[0], 'addresses': ['1/1/0']}]
        self.assertEqual(self.match('Luce bagno', paths, functions)['room'], paths[0])
        functions.append({'space': paths[1], 'addresses': ['1/1/0']})
        self.assertEqual(self.match('Luce bagno', paths, functions)['confidence'], 'ambiguous')

    def test_climate_uses_unique_setpoint_group_room_before_generic_labels(self):
        paths = ['Casa / Terra / Ambulatorio 1', 'Casa / Terra / Ambulatorio 2']
        spaces = [{'path': p, 'type': 'Room'} for p in paths]
        suggestions = [{'command': '1/1/0', 'name': 'Clima ambulatorio', 'kind': 'climate'}]
        addresses = [{'address': '1/1/0', 'group_name': 'Ambulatorio 2'}]
        match, = room_matches(suggestions, addresses, spaces, [])
        self.assertEqual((match['room'], match['confidence']), (paths[1], 'ets_group'))
        explicit = [{'space': paths[0], 'addresses': ['1/1/0']}]
        self.assertEqual(room_matches(suggestions, addresses, spaces, explicit)[0]['room'], paths[0])

    def test_fallback_sensor_gets_canonical_room(self):
        room = 'Casa / Terra / Cucina'
        data = {'building': [{'path': room, 'type': 'Room'}], 'addresses': [
            {'address': '1/1/0', 'name': 'Temperatura cucina', 'dpt': '9.001', 'linked': True}]}
        self.assertEqual(candidates(data)[0]['room'], room)

    def test_no_guess_from_thermostat_number_or_ambiguous_generic_room(self):
        paths = ['Casa / Primo / Camera nord', 'Casa / Primo / Camera sud']
        self.assertEqual(self.match('Termostato 2-4', paths)['confidence'], 'none')
        data = {'suggestions': [{'command': '1/1/0', 'name': 'Luce bagno', 'kind': 'light', 'room': 'Bagno'}],
                'building': [{'path': 'Casa / ' + floor + ' / Bagno', 'type': 'Room'} for floor in ['Terra', 'Primo']]}
        self.assertEqual(candidates(data)[0]['room'], 'Da assegnare')

    def test_multi_room_group_is_not_assigned_to_longest_name(self):
        paths = ['Casa / Terra / Cucina', 'Casa / Terra / Bagno ospiti']
        self.assertEqual(self.match('Generale cucina e bagno ospiti', paths)['confidence'], 'ambiguous')
