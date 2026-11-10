"""Recognize descriptive ETS circuit names without numbering conventions.

Only linked, unambiguous role/DPT pairs become fields. Names alone never
authorize installation. No customer-specific names or GA ranges are used.
"""
import re
import unicodedata


def normalized(value):
    text = unicodedata.normalize('NFKD', value.casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


# Longest/more specific suffixes precede shorter ones.
ROLES = (
    ('brightness_feedback', r'(?:(?:stato|sato) valore|valore (?:stato|sato))', {'5.001'}),
    ('brightness', r'(?:dimming assoluto|valore)', {'5.001'}),
    ('relative', r'(?:dimming relativo|dimmer)', {'3.007'}),
    ('feedback', r'(?:stato|sato) on\s*/\s*off', {'1.001', '1.011'}),
    ('position_feedback', r'(?:stato|sato) posizione attuale', {'5.001'}),
    ('position_command', r'posizione assoluta', {'5.001'}),
    ('stop', r'operazione breve\s*/\s*stop', {'1.007', '1.017'}),
    ('move', r'su\s*/\s*giu[\x27\u2019]?', {'1.008'}),
    ('command', r'on\s*/\s*off', {'1.001'}),
    ('feedback', r'(?:stato|sato)', {'1.001', '1.011'}),
)


def application_stop(item):
    """A manufacturer's explicit writable stop object can use DPT 1.008."""
    connections = item.get('connections', [])
    if any(c.get('size') and normalized(c['size']).replace(' ', '') not in ('1bit', '1bits')
           for c in connections):
        return False
    return any(c.get('flags', {}).get('WriteFlag') is True
               and normalized(c.get('size', '')).replace(' ', '') in ('1bit', '1bits')
               and c.get('dpt') in ('DPST-1-8', 'DPT-1.008')
               and re.search(r'\bstop\b|\barresto\b', normalized(c.get('function', '')))
               for c in connections)


def descriptive_suggestions(items):
    groups = {}
    for item in items:
        if not item.get('linked'):
            continue
        label = normalized(item.get('name', ''))
        for role, pattern, allowed in ROLES:
            match = re.fullmatch(r'(.+?)\s+' + pattern, label)
            if not match:
                continue
            stem = match[1].strip(' -')
            # Structured circuit naming has its own recognizer.
            if ' - ' in stem:
                break
            raw = str(item.get('dpt', '')).upper()
            dpt = re.fullmatch(r'(?:DPST-|DPT-)?(\d+)[.-](\d+)', raw)
            value = f'{int(dpt[1])}.{int(dpt[2]):03d}' if dpt else ''
            # A short state suffix describes either switching or level feedback.
            if pattern == r'(?:stato|sato)' and value == '5.001':
                role, allowed = 'brightness_feedback', {'5.001'}
            if role in ('brightness', 'relative', 'feedback', 'brightness_feedback'):
                stem = re.sub(r'\s+on\s*/\s*off$', '', stem)
            compatible = value in allowed or (role == 'stop' and value == '1.008' and application_stop(item))
            groups.setdefault(stem, {}).setdefault(role, []).append((item, compatible))
            break
    proposals, consumed = [], set()
    for stem, roles in groups.items():
        def one(role):
            entries = roles.get(role, [])
            return entries[0][0]['address'] if len(entries) == 1 and entries[0][1] else None
        move, command = one('move'), one('command')
        if move and command:
            continue
        if move and re.search(r'\b(?:tapparell\w*|tenda|serranda|shutter|blind)\b', stem):
            kind = 'cover'
            fields = {'command': move, **{key: one(key) for key in ('stop', 'position_command', 'position_feedback')}}
        elif command and (one('brightness') or one('relative')):
            kind = 'dimmer'
            fields = {'command': command, **{key: one(key) for key in ('feedback', 'brightness', 'brightness_feedback', 'relative')}}
        else:
            continue
        issues = [f'{role}: GA ambiguo o DPT non compatibile; verificare in ETS'
                  for role, entries in roles.items() if len(entries) != 1 or not entries[0][1]]
        fields = {key: value for key, value in fields.items() if value}
        collective = bool(re.search(r'\bgeneral[ei]\b|\bsx\s*/\s*dx\b', stem))
        proposals.append({'name': stem.upper(), 'kind': kind, **fields,
                          'room': 'Da assegnare', 'confidence': 'bassa' if issues else 'media',
                          'collective': collective,
                          'reason': 'Funzione da ruoli descrittivi e DPT; verificare oggetti collegati'
                                    + ('; comando collettivo' if collective else '')
                                    + ('; ' + '; '.join(issues) if issues else '')})
        consumed.update(fields.values())
    return proposals, consumed
