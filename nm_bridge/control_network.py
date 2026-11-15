"""Read-only HA network inventory. Never calls services or the UniFi controller."""
import math
import re

ENTITY = re.compile(r'^(sensor|binary_sensor)\.[a-z0-9_]+$')


def status(state, mode='link'):
    if not state or state.get('state') in ('unknown', 'unavailable', None):
        return 'Non disponibile'
    value = str(state['state']).lower()
    if mode == 'speed':
        try:
            number = float(value)
            if not math.isfinite(number) or number < 0:
                return 'Non disponibile'
            return 'Collegata' if number > 0 else 'Scollegata'
        except ValueError:
            return 'Non disponibile'
    return {'on': 'Collegata', 'off': 'Scollegata', 'up': 'Collegata',
            'down': 'Scollegata', 'connected': 'Collegata', 'disconnected': 'Scollegata'}.get(value, 'Non disponibile')


def sources(engine, payload):
    with engine.lock:
        engine.guard(payload, engine.layout_provider(), engine.read())
    with engine.connection_factory() as ws:
        devices = ws.call('config/device_registry/list')
        registry = ws.call('config/entity_registry/list')
        states = {s['entity_id']: s for s in ws.call('get_states')}
    unifi_ids = {e.get('device_id') for e in registry if e.get('platform') == 'unifi'}
    result = []
    for d in devices:
        if d['id'] not in unifi_ids:
            continue
        entries = []
        for ent in registry:
            eid = ent['entity_id']
            if ent.get('device_id') != d['id'] or ent.get('platform') != 'unifi' or not ENTITY.fullmatch(eid):
                continue
            s = states.get(eid, {})
            a = s.get('attributes') or {}
            entries.append({'id': eid, 'name': a.get('friendly_name') or ent.get('name') or ent.get('original_name') or eid,
                            'state': s.get('state', 'unavailable'), 'unit': a.get('unit_of_measurement', ''),
                            'disabled': bool(ent.get('disabled_by'))})
        result.append({'id': d['id'], 'name': d.get('name_by_user') or d.get('name') or d['id'],
                       'model': d.get('model') or '', 'entities': entries})
    return {'devices': result}


def readings(states):
    return {s['entity_id']: {'state': s.get('state'), 'unit': (s.get('attributes') or {}).get('unit_of_measurement', '')}
            for s in states if ENTITY.fullmatch(s.get('entity_id', ''))}
