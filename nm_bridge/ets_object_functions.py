"""Provisional function recognition from linked application objects.

Never group by GA proximity, device alone or object-number arithmetic. An
explicit module instance and unambiguous DPT/direction roles are required.
"""
import re


def dpt(value):
    match = re.fullmatch(r'(?:DPST-|DPT-)?(\d+)[.-](\d+)', str(value or '').upper())
    return f'{int(match[1])}.{int(match[2]):03d}' if match else ''


AC_ROLES = {
    'on/off': ('1.001', 'on_off', 'on_off_state'),
    'temperature setpoint': ('9.001', 'command', 'target_temperature_state'),
    'indoor unit temperature': ('9.001', None, 'temperature'),
    'mode': ('20.105', 'controller_mode', 'controller_mode_state'),
    'speed: percentage control': ('5.001', 'fan_speed', 'fan_speed_state'),
    'flaps: swing': ('1.001', 'swing', 'swing_state'),
    'speed: automatic': ('1.003', 'fan_auto', 'fan_auto_state'),
    'flaps: percentage control': ('5.001', 'flap_position', 'flap_position_state'),
    'automatic off': ('1.001', 'suspend', 'suspend_state'),
    'automatic off: delay': ('7.005', 'suspend_delay', None),
    'filter: reset': ('1.017', 'filter_reset', None),
    'filter': ('1.002', None, 'filter_alarm'),
}


AC_ACCESSORIES = {
    'fan_auto': ('switch', 'Ventola automatica', 'fan_auto_state'),
    'flap_position': ('number', 'Posizione lamelle (0% = swing)', 'flap_position_state'),
    'suspend': ('switch', 'Sospensione temporanea', 'suspend_state'),
    'suspend_delay': ('number', 'Ritardo sospensione (s)', None),
    'filter_reset': ('button', 'Reset filtro', None),
    'filter_alarm': ('binary_sensor', 'Filtro da pulire', None),
}

AC_POLARITIES = {
    'fan_auto': ('automatic on', r'automatic off(?: \(speed 1\))?'),
    'fan_auto_state': ('automatic on', 'automatic off'),
    'suspend': ('activate', 'deactivate'),
    'suspend_state': ('activated', 'deactivated'),
    'filter_alarm': ('alarm', 'no alarm'),
}


def climate_role(obj):
    """Resolve explicit catalogue semantics, never infer state from transmit alone."""
    label = ' '.join(obj.get('text', '').casefold().split())
    match = re.fullmatch(r'\[ac\] (.+?)( \(status\))?', label)
    if match and match[1] in AC_ROLES:
        expected, command, state = AC_ROLES[match[1]]
        reporting = bool(match[2])
        return expected, state if reporting else command, reporting, False
    match = re.fullmatch(r'(control|status)_ (.+) \[dpt_(\d+\.\d+)\]', label)
    if not match:
        return None
    roles = {
        'on/off': ('1.001', 'on_off', 'on_off_state'),
        'mode': ('20.105', 'controller_mode', 'controller_mode_state'),
        'setpoint temperature': ('9.001', 'command', None),
        'ac setpoint temperature': ('9.001', None, 'target_temperature_state'),
        'ac reference temperature': ('9.001', None, 'temperature'),
    }
    entry = roles.get(match[2])
    if re.fullmatch(r'fan speed / [2345] speeds', match[2]):
        entry = ('5.001', 'fan_speed', 'fan_speed_state')
    if not entry or dpt(match[3]) != entry[0]:
        return None
    expected, command, state = entry
    reporting = match[1] == 'status'
    return expected, state if reporting else command, reporting, True


def ac_polarity(role, function):
    active, inactive = AC_POLARITIES[role]
    text = ' '.join(function.casefold().split())
    if re.fullmatch(fr'0 = {inactive}; 1 = {active}', text):
        return 'normal'
    if re.fullmatch(fr'0 = {active}; 1 = {inactive}', text):
        return 'inverted'
    return ''


def ac_accessories(fields, polarities, name):
    accessories = []
    for role, (kind, label, feedback) in AC_ACCESSORIES.items():
        if role not in fields or (feedback and feedback not in fields):
            continue
        profile = role
        if role in AC_POLARITIES:
            values = polarities.get(role)
            if feedback and values != polarities.get(feedback):
                continue
            if values == {'inverted'} and kind == 'switch':
                profile += '_inverted'
            elif values != {'normal'}:
                continue
        item = dict(kind=kind, profile=profile, name=f'{label} · {name}'[:80], command=fields[role],
                    confidence='alta', reason='Funzione ausiliaria verificata dagli oggetti del gateway ETS')
        if feedback:
            item['feedback'] = fields[feedback]
        accessories.append(item)
    return accessories


def object_climates(items, conflicts=None):
    """Recognize an AC gateway by explicit application roles and direction."""
    devices, polarities, owners = {}, {}, {}
    labels = {item['address']: item['name'] for item in items}
    group_labels = {item['address']: item.get('group_name', '') for item in items}
    for item in items:
        if not item.get('linked'):
            continue
        for obj in item.get('connections', []):
            entry = climate_role(obj)
            # Only flat gateway objects here. Module instances may represent
            # different units on one physical device and must not be combined.
            if not entry or not obj.get('device_id') or not re.fullmatch(r'O-\d+_R-\d+', obj.get('object_ref', '')):
                continue
            expected, role, reporting, bidirectional_command = entry
            if not role:
                continue
            flags = obj.get('flags', {})
            if (dpt(item.get('dpt')) != expected or dpt(obj.get('dpt')) != expected
                    or flags.get('CommunicationFlag') is not True
                    or flags.get('WriteFlag') is not (not reporting)
                    or (reporting and flags.get('TransmitFlag') is not True)
                    or (not reporting and not bidirectional_command and flags.get('TransmitFlag') is not False)):
                continue
            device = obj['device_id']
            owners.setdefault(item['address'], set()).add(device)
            devices.setdefault(device, {}).setdefault(role, set()).add(item['address'])
            if role in AC_POLARITIES:
                polarities.setdefault(device, {}).setdefault(role, set()).add(
                    ac_polarity(role, obj.get('function', '')))

    candidates = []
    required = {'command', 'target_temperature_state', 'temperature', 'on_off', 'on_off_state'}
    core_roles = {role for entry in AC_ROLES.values() for role in entry[1:] if role}
    accessory_roles = AC_ACCESSORIES.keys() | {entry[2] for entry in AC_ACCESSORIES.values()}
    core_roles -= accessory_roles
    # Collapse only identical complete role maps. Sharing just an ON/OFF GA
    # does not prove that two independently configured zones form one unit.
    groups = {}
    for device, roles in devices.items():
        signature = tuple(sorted((role, tuple(sorted(values))) for role, values in roles.items()))
        groups.setdefault(signature, []).append(device)
    for members in groups.values():
        device = members[0]
        roles = devices[device]
        fields = {role: next(iter(addresses)) for role, addresses in roles.items() if len(addresses) == 1}
        core = {role: fields[role] for role in core_roles if role in fields}
        # A command-only ventilation gateway remains a visible incomplete draft.
        command_bundle = {'command', 'on_off', 'controller_mode', 'fan_speed'}
        if (not required.issubset(core) and not command_bundle.issubset(core)) or len(set(core.values())) != len(core):
            continue
        name = group_labels.get(core['command']) or re.sub(r'\s+on\s*/\s*off\s*$', '', labels[core['on_off']], flags=re.I).strip()
        shared = {address for address in fields.values() if len(owners[address]) > 1}
        collective = len(members) > 1 and all(owners[a] == set(members) for a in fields.values())
        command = core['command']
        shared_primary = bool({command, core['on_off']}.intersection(shared))
        missing = sorted(required - core.keys())
        if (shared or missing) and conflicts is not None:
            conflict = dict(name=name, command=command, addresses=sorted(shared), shared_primary=shared_primary,
                            collective=collective, missing=missing)
            if conflict not in conflicts:
                conflicts.append(conflict)
        if shared_primary and not collective:
            continue
        # An ETS feedback sent by several gateways is not the state of one room.
        # Keep the climate draft visible, with shared roles to review explicitly.
        for _, write, state in AC_ROLES.values():
            if not collective and (core.get(write) in shared or core.get(state) in shared):
                if write not in ('command', 'on_off'):
                    core.pop(write, None)
                core.pop(state, None)
        available = {role: address for role, address in fields.items()
                     if role in accessory_roles and (collective or address not in shared)
                     and list(fields.values()).count(address) == 1}
        group_polarities = {}
        for member in members:
            for role, values in polarities.get(member, {}).items():
                group_polarities.setdefault(role, set()).update(values)
        accessories = ac_accessories(available, group_polarities, name)
        reason = 'Ruoli clima e DPT dagli oggetti del gateway ETS'
        if collective:
            reason += '; gruppo con comandi comuni: gli stati riportano l’ultimo telegramma ricevuto, non una media o uno stato aggregato'
        if missing:
            reason += '; da completare: ' + ', '.join(missing)
        candidate = dict(name=f"CLIMA {name}", kind='climate', **core, room='Da assegnare',
                         collective=collective, confidence='bassa' if missing else 'media', reason=reason)
        if accessories:
            candidate['accessories'] = accessories
        candidates.append(candidate)
    return candidates


def object_dimmers(items):
    groups = {}
    labels = {a['address']: a.get('name') or a['address'] for a in items}
    for item in items:
        if not item.get('linked'):
            continue
        for obj in item.get('connections', []):
            ref = obj.get('object_ref', '')
            # Preserve every module-instance component, including nesting.
            prefix = ref.split('_O-', 1)[0]
            if '_O-' not in ref or not re.search(r'(?:^|_)MI-\d+(?:_|$)', prefix):
                continue
            if not obj.get('device_id'):
                continue
            scope = (obj['device_id'], prefix)
            roles = groups.setdefault(scope, {})
            value, declared = dpt(obj.get('dpt')), dpt(item.get('dpt'))
            flags = obj.get('flags', {})
            # Contradictions veto the scope instead of selecting a convenient link.
            if (declared and value and declared != value):
                roles.setdefault('conflict', set()).add(item['address'])
                continue
            value = declared or value
            if value in ('1.008', '3.008', '9.001', '20.102'):
                # A multi-function module isn't necessarily one lighting channel.
                roles.setdefault('conflict', set()).add(item['address'])
                continue
            if flags.get('CommunicationFlag') is not True:
                continue
            writable = flags.get('WriteFlag') is True and flags.get('TransmitFlag') is False
            reporting = flags.get('WriteFlag') is False and flags.get('TransmitFlag') is True
            if not (writable or reporting):
                continue
            mapping = {'1.001': ('command', 'feedback'),
                       '1.011': (None, 'feedback'),
                       '3.007': ('relative', None),
                       '5.001': ('brightness', 'brightness_feedback')}
            if value not in mapping:
                continue
            expected_size = {'1': ('1bit', '1bits'), '3': ('4bit', '4bits'),
                             '5': ('1byte', '1bytes', '8bit', '8bits')}[value.split('.')[0]]
            size = str(obj.get('size') or '').lower().replace(' ', '')
            if size and size not in expected_size:
                roles.setdefault('conflict', set()).add(item['address'])
                continue
            role = mapping[value][0 if writable else 1]
            if role:
                roles.setdefault(role, set()).add(item['address'])

    by_command = {}
    for scope, roles in groups.items():
        # Relative dimming is the functional evidence; a percentage alone isn't.
        if 'conflict' in roles or len(roles.get('command', ())) != 1 or len(roles.get('relative', ())) != 1:
            continue
        fields = {role: next(iter(values)) for role, values in roles.items() if len(values) == 1}
        if len(set(fields.values())) != len(fields):
            continue
        by_command.setdefault(fields['command'], []).append((scope, roles, fields))
    proposals = []
    for command, candidates in by_command.items():
        fields, ambiguous = {}, set()
        for _, roles, _ in candidates:
            for role, values in roles.items():
                if len(values) != 1:
                    ambiguous.add(role)
                fields.setdefault(role, set()).update(values)
        ambiguous.update(role for role, values in fields.items() if len(values) != 1)
        chosen = {role: next(iter(values)) for role, values in fields.items() if role not in ambiguous}
        if 'relative' not in chosen:
            continue
        proposals.append(dict(name=labels[command], kind='dimmer', **chosen,
                              room='Da assegnare', confidence='bassa' if ambiguous else 'media',
                              collective=len(candidates) > 1,
                              reason='DPT e flag degli oggetti collegati nella stessa istanza modulo; verificare in ETS'
                              + ''.join(f'; {role}: associazione ambigua' for role in sorted(ambiguous))))
    return proposals


def enrich_suggestions(items, suggestions):
    """Keep manual-review conflicts visible and never overwrite a prior mapping."""
    result = [dict(s) for s in suggestions]
    candidates = object_dimmers(items)
    commands = {s['command'] for s in candidates}
    auxiliary = {s[field] for s in candidates
                 for field in ('feedback', 'brightness', 'brightness_feedback', 'relative') if field in s}
    result = [s for s in result if s['command'] not in auxiliary
              or s['command'] in commands or s['kind'] not in ('unknown', 'binary')]
    for candidate in candidates:
        existing = [s for s in result if s['command'] == candidate['command']]
        if existing:
            for target in existing:
                if target['kind'] not in ('unknown', 'binary', 'light', 'dimmer'):
                    continue
                for field in ('feedback', 'brightness', 'brightness_feedback', 'relative'):
                    if field not in candidate or f'{field}:' in target.get('reason', ''):
                        continue
                    if target.get(field) and target[field] != candidate[field]:
                        target['confidence'] = 'bassa'
                        target['reason'] = target.get('reason', '') + f'; {field}: nomi e oggetti discordanti'
                    else:
                        target[field] = candidate[field]
                target['kind'] = 'dimmer'
                target['collective'] = target.get('collective', False) or candidate['collective']
                target['reason'] = target.get('reason', '') + '; ' + candidate['reason']
                if candidate['confidence'] == 'bassa':
                    target['confidence'] = 'bassa'
        else:
            result.append(candidate)
    return result
