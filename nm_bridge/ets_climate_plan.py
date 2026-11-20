"""Prepare offline HVAC associations from KNX communication-object links."""

import hashlib
import json
import re
from collections import defaultdict

try:
    from .recognition import _dpt
except ImportError:
    from recognition import _dpt


# This ETS application encodes the communication object number in O-<number>.
# The reference fallback also supports projects saved before catalogue metadata
# for this application could fit the import size limit.
APPLICATION = 'M-0071/M-0071_A-12D1-15-12D0.xml'
POINTS = {
    2: ('on_off_address', '1.001', 'Accensione', 'WriteFlag'),
    3: ('on_off_state_address', '1.001', 'Stato accensione', 'TransmitFlag'),
    4: ('target_temperature_address', '9.001', 'Setpoint', 'WriteFlag'),
    5: ('target_temperature_state_address', '9.001', 'Stato setpoint', 'TransmitFlag'),
    10: ('controller_mode_address', '20.105', 'Modalità', 'WriteFlag'),
    11: ('controller_mode_state_address', '20.105', 'Stato modalità', 'TransmitFlag'),
    14: ('fan_speed_address', '5.001', 'Velocità ventola', 'WriteFlag'),
    15: ('fan_speed_state_address', '5.001', 'Stato velocità ventola', 'TransmitFlag'),
    16: ('fan_auto', '1.003', 'Ventola automatica', 'WriteFlag'),
    17: ('fan_auto_state', '1.003', 'Stato ventola automatica', 'TransmitFlag'),
    18: ('vane_position', '5.001', 'Posizione palette', 'WriteFlag'),
    19: ('vane_position_state', '5.001', 'Stato posizione palette', 'TransmitFlag'),
    20: ('swing_address', '1.001', 'Oscillazione palette', 'WriteFlag'),
    21: ('swing_state_address', '1.001', 'Stato oscillazione palette', 'TransmitFlag'),
    24: ('temperature_address', '9.001', 'Temperatura unità interna', 'TransmitFlag'),
    36: ('filter_reset', '1.017', 'Reset filtro', 'WriteFlag'),
    37: ('filter_alarm', '1.002', 'Allarme filtro', 'TransmitFlag'),
}
CORE = (2, 3, 4, 5, 10, 11, 24)
MODES = ['auto', 'heat', 'cool', 'fan_only', 'dry', 'off']


def _point_map(unit, device, inventory):
    if device.get('program') != APPLICATION:
        return {}
    by_number = defaultdict(set)
    for point in unit['points']:
        address = inventory.get(point['address'], {})
        for connection in address.get('connections', []):
            if connection.get('device_id') != unit['device_id']:
                continue
            # Match an actual instance reference, not an address naming pattern.
            ref = re.fullmatch(r'O-(\d+)_R-\d+', connection.get('object_ref', ''))
            number = int(ref[1]) if ref else -1
            if number not in POINTS:
                continue
            _, dpt, _, flag = POINTS[number]
            types = [value for value in (address.get('dpt'), connection.get('dpt')) if value]
            flags = connection.get('flags', {})
            if (types and all(_dpt(value) == dpt for value in types)
                    and flags.get(flag, True) and flags.get('CommunicationFlag', True)):
                by_number[number].add(point['address'])
    return {number: next(iter(addresses)) for number, addresses in by_number.items() if len(addresses) == 1}


def _shared_groups(units):
    groups = defaultdict(list)
    for unit in units:
        for point in unit['points']:
            if point['shared_hvac']:
                groups[point['address']].append((unit, point))
    sets = defaultdict(list)
    for address, links in groups.items():
        peers = tuple(unit['individual_address'] for unit, _ in links)
        sets[peers].append({'address': address, 'label': links[0][1]['label'],
                           'direction': links[0][1]['direction']})
    by_id = {u['individual_address']: u for u in units}
    return [{'devices': list(peers), 'rooms': sorted({r for p in peers for r in by_id[p]['rooms']}),
             'points': points} for peers, points in sets.items()]


def build(imported):
    units = sorted(imported.get('hvac_units', []), key=lambda u: u['individual_address'])
    devices = {d['id']: d for d in imported.get('devices', [])}
    inventory = {a['address']: a for a in imported.get('addresses', [])}
    shared = _shared_groups(units)
    group_by_ga = {p['address']: set(group['devices']) for group in shared for p in group['points']}
    maps = {u['device_id']: _point_map(u, devices.get(u['device_id'], {}), inventory)
            for u in units if u['kind'] == 'climate'}
    profiles = defaultdict(list)
    for unit in units:
        points = maps.get(unit['device_id'], {})
        if all(n in points for n in CORE):
            profiles[tuple(points[n] for n in CORE)].append(unit)

    project = imported['project_key']
    package = defaultdict(list)
    cards = {}
    targets = {}
    for members in profiles.values():
        points = maps[members[0]['device_id']]
        room_names = sorted({r.rsplit(' / ', 1)[-1] for u in members for r in u['rooms']})
        label = ' / '.join(room_names) or members[0]['individual_address']
        identity = members[0]['individual_address']
        id_seed = project + ':' + identity
        slug = 'nm_knx_' + hashlib.sha256(id_seed.encode()).hexdigest()[:12]

        def entry(platform, name, fields, suffix=''):
            ident = slug + suffix
            entity = platform + '.' + ident
            package[platform].append({'name': name, 'unique_id': ident, 'default_entity_id': entity, **fields})
            return entity

        def private_pair(command, state):
            return all(n in points and points[n] not in group_by_ga for n in (command, state))

        # A shared primary address is usable in the draft only when all
        # participants have the exact same primary mapping. Temperature can be
        # a common feedback channel, and is made explicit in each preview.
        member_ids = {u['individual_address'] for u in members}
        if any(points[n] in group_by_ga and not group_by_ga[points[n]].issubset(member_ids)
               for n in CORE if POINTS[n][3] == 'WriteFlag'):
            continue

        fields = {POINTS[n][0]: points[n] for n in CORE}
        fields.update(min_temp=16, max_temp=32, temperature_step=1,
                      controller_modes=['auto', 'heat', 'cool', 'fan_only', 'dehumidification'])
        if private_pair(14, 15):
            fields.update(fan_speed_address=points[14], fan_speed_state_address=points[15], fan_zero_mode='auto')
        if private_pair(20, 21):
            fields.update(swing_address=points[20], swing_state_address=points[21])
        live = {'type': 'custom:nm-climate-card', 'project': project,
                'entity': entry('climate', 'Clima ' + label, fields)}
        if private_pair(16, 17):
            live['fan_auto'] = entry('switch', 'Ventola automatica ' + label,
                                     {'address': points[16], 'state_address': points[17], 'invert': True}, '_auto')
        if private_pair(18, 19):
            live['vane_position'] = entry('number', 'Posizione palette ' + label,
                                          {'address': points[18], 'state_address': points[19], 'type': 'percent',
                                           'min': 0, 'max': 100, 'step': 20}, '_palette')
        if 37 in points and points[37] not in group_by_ga:
            live['filter_alarm'] = entry('binary_sensor', 'Allarme filtro ' + label,
                                        {'state_address': points[37]}, '_filtro')
        if 36 in points and points[36] not in group_by_ga:
            live['filter_reset'] = entry('button', 'Reset filtro ' + label, {'address': points[36]}, '_reset')
        for unit in members:
            name = ' / '.join(r.rsplit(' / ', 1)[-1] for r in unit['rooms']) or identity
            targets[unit['individual_address']] = {**live, 'name': 'Clima · ' + name}

    for unit in units:
        if unit['kind'] != 'climate':
            continue
        points = maps[unit['device_id']]
        members = profiles.get(tuple(points.get(n) for n in CORE), [])
        label = ' / '.join(sorted({r.rsplit(' / ', 1)[-1] for u in members for r in u['rooms']}))
        target = targets.get(unit['individual_address'])
        details = [{'label': POINTS[n][2], 'address': address, 'shared': address in group_by_ga,
                    'direction': 'Comando' if POINTS[n][3] == 'WriteFlag' else 'Stato'}
                   for n, address in sorted(points.items())]
        cards[unit['device_id']] = {
            'type': 'custom:nm-climate-card', 'project': project,
            'commissioning': {'individual_address': unit['individual_address'], 'points': details,
                              'modes': MODES if target else [], 'joint_zone': label if len(members) > 1 else '',
                              'planned_entity': target['entity'] if target else ''},
            'grid_options': {'columns': 12},
        }

    lines = [
        '# Bozza NM Control da ETS. Confrontare con il registro KNX prima di installare.',
        '# I punti condivisi richiedono collaudo sul bus, inclusa la provenienza degli stati.',
        '# Le uscite accessorie condivise sono escluse dalla configurazione.',
    ]
    for group in shared:
        lines.append('# GA condivisi: ' + ', '.join(group['devices']) + ' · '
                     + ', '.join(point['address'] for point in group['points']))
    lines.append('knx:' if package else 'knx: {}')
    for platform, entries in package.items():
        lines.append('  ' + platform + ':')
        for row in entries:
            for i, (key, value) in enumerate(row.items()):
                lines.append(('    - ' if i == 0 else '      ') + key + ': ' + json.dumps(value, ensure_ascii=False))
    return {'cards': cards, 'shared_groups': shared, 'associations': list(package.get('climate', [])),
            'popup_configs': targets, 'ha_yaml': '\n'.join(lines) + '\n'}
