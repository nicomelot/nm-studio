"""Provisional dimmer recognition from linked application objects, without GA names.

Never group by GA proximity, device alone or object-number arithmetic. An
explicit module instance and unambiguous DPT/direction roles are required.
"""
import re


def dpt(value):
    match = re.fullmatch(r'(?:DPST-|DPT-)?(\d+)[.-](\d+)', str(value or '').upper())
    return f'{int(match[1])}.{int(match[2]):03d}' if match else ''


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
