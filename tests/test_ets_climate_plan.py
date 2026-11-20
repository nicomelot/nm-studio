import unittest

from nm_bridge.ets_climate_plan import APPLICATION, POINTS, build


def mapped_project():
    devices, units, addresses = [], [], {}
    for index, group in enumerate((1, 1, 2, 3, 4)):
        device = f'device-{index}'
        devices.append({'id': device, 'program': APPLICATION})
        unit = {'device_id': device, 'individual_address': f'1.1.{index + 1}',
                'kind': 'climate', 'rooms': [f'Zona {index + 1}'], 'points': []}
        units.append(unit)
        for number, (_, dpt, label, flag) in POINTS.items():
            main, sub = dpt.split('.')
            raw_dpt = f'DPST-{main}-{int(sub)}'
            prefix = 2 if group == 3 and number in (14, 15, 24, 36, 37) else group
            ga = f'{prefix}/0/{number}'
            point = {'address': ga, 'label': label, 'direction': 'command' if flag == 'WriteFlag' else 'state',
                     'shared_hvac': prefix == 1 or (prefix == 2 and number in (14, 15, 24, 36, 37))}
            unit['points'].append(point)
            address = addresses.setdefault(ga, {'address': ga, 'dpt': raw_dpt, 'connections': []})
            address['connections'].append({'device_id': device, 'object_ref': f'O-{number}_R-1', 'dpt': raw_dpt})
    return {'project_key': 'a' * 64, 'devices': devices, 'hvac_units': units, 'addresses': list(addresses.values())}


class ClimatePlanTests(unittest.TestCase):
    def test_identical_primary_addresses_share_entity_partial_pair_has_own_setpoint(self):
        plan = build(mapped_project())
        configs = plan['popup_configs']
        self.assertEqual(len(plan['associations']), 4)
        self.assertEqual(configs['1.1.1']['entity'], configs['1.1.2']['entity'])
        self.assertNotEqual(configs['1.1.3']['entity'], configs['1.1.4']['entity'])
        climate = next(row for row in plan['associations'] if row['default_entity_id'] == configs['1.1.4']['entity'])
        self.assertEqual(climate['target_temperature_address'], '3/0/4')
        self.assertEqual(climate['temperature_address'], '2/0/24')
        self.assertNotIn('fan_speed_address', climate)
        self.assertNotIn('filter_reset', configs['1.1.4'])
        self.assertIn('vane_position', configs['1.1.4'])
        self.assertTrue(all('entity' not in c for c in plan['cards'].values()))
        self.assertIn('"dehumidification"', plan['ha_yaml'])

    def test_dpt_conflict_prevents_complete_association(self):
        project = mapped_project()
        address = next(a for a in project['addresses'] if a['address'] == '3/0/11')
        address['dpt'] = 'DPST-20-102'
        plan = build(project)
        self.assertNotIn('1.1.4', plan['popup_configs'])
        self.assertEqual(plan['cards']['device-3']['commissioning']['planned_entity'], '')
