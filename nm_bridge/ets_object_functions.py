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


def object_climates(items):
    """Recognize an AC gateway by explicit application roles and direction."""
    devices, polarities = {}, {}
    labels = {item['address']: item['name'] for item in items}
    for item in items:
        if not item.get('linked'):
            continue
        for obj in item.get('connections', []):
            label = ' '.join(obj.get('text', '').casefold().split())
            match = re.fullmatch(r'\[ac\] (.+?)( \(status\))?', label)
            # Only flat gateway objects here. Module instances may represent
            # different units on one physical device and must not be combined.
            if not match or not obj.get('device_id') or not re.fullmatch(r'O-\d+_R-\d+', obj.get('object_ref', '')):
                continue
            entry = AC_ROLES.get(match[1])
            if not entry:
                continue
            expected, command, state = entry
            reporting = bool(match[2])
            role = state if reporting else command
            if not role:
                continue
            flags = obj.get('flags', {})
            if (dpt(item.get('dpt')) != expected or dpt(obj.get('dpt')) != expected
                    or flags.get('CommunicationFlag') is not True
                    or flags.get('WriteFlag') is not (not reporting)
                    or flags.get('TransmitFlag') is not reporting):
                continue
            device = obj['device_id']
            devices.setdefault(device, {}).setdefault(role, set()).add(item['address'])
            if role in AC_POLARITIES:
                polarities.setdefault(device, {}).setdefault(role, set()).add(
                    ac_polarity(role, obj.get('function', '')))

    candidates = []
    required = {'command', 'target_temperature_state', 'temperature', 'on_off', 'on_off_state'}
    core_roles = {role for entry in AC_ROLES.values() for role in entry[1:] if role}
    core_roles -= AC_ACCESSORIES.keys() | {entry[2] for entry in AC_ACCESSORIES.values()}
    for device, roles in devices.items():
        fields = {role: next(iter(addresses)) for role, addresses in roles.items() if len(addresses) == 1}
        core = {role: fields[role] for role in core_roles if role in fields}
        if not required.issubset(core) or len(set(core.values())) != len(core):
            continue
        name = re.sub(r'\s+on\s*/\s*off\s*$', '', labels[core['on_off']], flags=re.I).strip()
        available = {role: address for role, address in fields.items()
                     if role not in core and list(fields.values()).count(address) == 1}
        accessories = ac_accessories(available, polarities.get(device, {}), name)
        candidate = dict(name=f"CLIMA {name}", kind='climate', **core, room='Da assegnare',
                         confidence='media', reason='Ruoli AC e DPT dagli oggetti di uno stesso gateway ETS')
        if accessories:
            candidate['accessories'] = accessories
        candidates.append(candidate)
    # A shared primary command does not identify a single unit.
    return [c for c in candidates if not any(
        other is not c and (other['command'] == c['command'] or other['on_off'] == c['on_off'])
        for other in candidates)]


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
