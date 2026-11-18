"""Read HVAC evidence from ETS topology and actual group address links."""

import re
from collections import defaultdict

try:
    from .ets_rooms import normalized
    from .recognition import _dpt
except ImportError:
    from ets_rooms import normalized
    from recognition import _dpt


# Exact product references identify the appliance interfaces even when ETS
# doesn't export communication object labels or no objects have been linked.
MODELS = {
    ('M-0071', 'ZCLDIV2'): ('climate', 'Zennio KLIC-DI v2'),
    ('M-0077', 'DK.2DRC.2DKNX.2D1i'): ('gateway', 'DK-RC-KNX-1i'),
}

# Match specific functions before simple on/off and status. Using both label
# and DPT keeps e.g. the HVAC controller mode (20.105) distinct from a preset.
ROLES = (
    (r'\b(?:set\s*point|target temperature)\b', ('9.001',), 'Setpoint', True),
    (r'\b(?:temperatura (?:unita interna|ambiente|attuale|misurata)|room temperature|ambient temperature)\b',
     ('9.001',), 'Temperatura ambiente', False),
    (r'\b(?:modalita|mod|mode)\b', ('20.105',), 'Modalità clima', True),
    (r'\b(?:velocita (?:ventola )?automatic[oa]|fan automatic|automatic fan|fan auto)\b',
     ('1.001', '1.003'), 'Ventola automatica', True),
    (r'\b(?:velocita|fan speed|fan percentage)\b', ('5.001',), 'Velocità ventola', True),
    (r'\b(?:lamelle|alette|flaps|vanes)\b', ('5.001',), 'Posizione lamelle', True),
    (r'\bswing\b', ('1.001',), 'Swing lamelle', True),
    (r'\b(?:off automatico ritardo|automatic off delay)\b', ('7.005',), 'Ritardo spegnimento automatico', True),
    (r'\b(?:off automatico|automatic off)\b', ('1.001',), 'Spegnimento automatico', True),
    (r'\b(?:filtro reset|reset filtro|filter reset|reset filter)\b', ('1.017',), 'Reset filtro', True),
    (r'\b(?:filtro|filter)\b', ('1.002',), 'Stato filtro', False),
    (r'\bon off\b', ('1.001',), 'Accensione', True),
)
STATUS = re.compile(r'\b(?:stato|status|feedback)\b')
MAX_REPORTED_PEERS = 8


def model(product_ref):
    manufacturer, _, _ = product_ref.partition('_')
    return MODELS.get((manufacturer, product_ref.rsplit('_P-', 1)[-1]))


def classify(address, device_id):
    # The project GA name is primary evidence. Catalog labels are a fallback
    # when the installer uses abbreviated or unnamed group addresses.
    names = [address['name']]
    objects = [obj for obj in address['connections'] if obj['device_id'] == device_id]
    names.extend(obj.get('name', '') for obj in objects)
    dpt = _dpt(address['dpt'])
    if not address['dpt']:
        types = {_dpt(obj.get('dpt')) for obj in objects}
        if len(types) == 1:
            dpt = types.pop()
    ga_status = bool(STATUS.search(normalized(address['name'])))
    for raw_name in names:
        name = normalized(raw_name)
        status = ga_status or bool(STATUS.search(name))
        for pattern, allowed, label, writable in ROLES:
            if dpt in allowed and re.search(pattern, name):
                if status and writable:
                    return f'{label} · stato', 'state'
                return label, 'command' if writable else 'state'
    if dpt == '1.001' and ga_status and not re.search(r'\b(?:filtro|filter)\b', normalized(address['name'])):
        return 'Stato accensione da verificare', 'state'
    return 'Funzione da verificare', 'unknown'


def inspect_hvac(devices, addresses, spaces, links):
    locations = defaultdict(set)
    for space in spaces:
        for ets_id in space['devices']:
            locations[ets_id].add(space['path'])
    by_device = {device['id']: device for device in devices}
    units = {}
    for device in devices:
        family = model(device['product_ref'])
        if not family:
            continue
        kind, label = family
        units[device['id']] = {
            'device_id': device['id'], 'name': device['name'], 'model': label, 'kind': kind,
            'individual_address': device.get('individual_address', ''),
            'rooms': sorted(locations[device['ets_id']]), 'points': [],
        }

    # Use the complete address-to-device index, not the display list of at
    # most twelve communication objects on each GA.
    for address in addresses:
        linked = links.get(address['address'], set())
        hvac_ids = linked & units.keys()
        if not hvac_ids:
            continue
        peers = sorted(linked, key=lambda device_id: (device_id not in units, device_id))
        for device_id in sorted(hvac_ids):
            label, direction = classify(address, device_id)
            others = []
            for other_id in peers[:MAX_REPORTED_PEERS + 1]:
                if other_id == device_id or len(others) >= MAX_REPORTED_PEERS:
                    continue
                other = by_device[other_id]
                others.append({
                    'name': other['name'], 'individual_address': other.get('individual_address', ''),
                    'rooms': sorted(locations[other['ets_id']]),
                    'hvac': other_id in units,
                })
            units[device_id]['points'].append({
                'address': address['address'], 'name': address['name'], 'dpt': address['dpt'],
                'label': label, 'direction': direction, 'shared_with': others,
                'peer_count': len(linked) - 1, 'shared_hvac': len(hvac_ids) > 1,
            })
    return list(units.values())


def known_hvac_addresses(units):
    return {point['address'] for unit in units for point in unit['points'] if point['direction'] != 'unknown'}
