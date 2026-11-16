"""Independent date exceptions; the seven weekly helpers are never rewritten."""
import json
import re
from datetime import date, datetime, timezone

KINDS = {'v': 'Ferie', 'f': 'Festivi'}


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Data non valida')
    return date.fromisoformat(value)


def validate_meta(meta):
    if not isinstance(meta, dict) or type(meta.get('enabled')) is not bool:
        raise ValueError('Profilo non valido')
    if not re.fullmatch('[a-f0-9]{32}', str(meta.get('v', ''))):
        raise ValueError('Versione profilo non valida')
    if meta.get('kind') == 'v':
        if parse_date(meta.get('start')) > parse_date(meta.get('end')):
            raise ValueError('La fine ferie precede l’inizio')
    elif meta.get('kind') == 'f':
        dates = meta.get('dates')
        if not isinstance(dates, list) or not 1 <= len(dates) <= 10 or len(set(dates)) != len(dates):
            raise ValueError('Scegli da 1 a 10 date festive distinte')
        for item in dates:
            parse_date(item)
    else:
        raise ValueError('Tipo profilo non valido')
    return meta


def selected_profile(calendar, day):
    value = day.isoformat()
    vacation = calendar.get('v', {})
    holiday = calendar.get('f', {})
    if vacation.get('enabled') and vacation['start'] <= value <= vacation['end']:
        return 'v'
    if holiday.get('enabled') and value in holiday['dates']:
        return 'f'
    return 'w'


def load_profiles(row, inventory):
    result = {}
    for kind, ids in row.get('calendar', {}).get('profiles', {}).items():
        value = inventory.get(ids[0], {}).get('state')
        if value in (None, '', 'unknown'):
            continue
        try:
            meta = json.loads(value)
            if meta.get('enabled') is False:
                continue
            validate_meta(meta)
            if meta['kind'] != kind:
                raise ValueError('Tipo profilo diverso')
            slots = json.loads(inventory.get(ids[1], {}).get('state', ''))
            if slots.get('v') != meta['v']:
                raise ValueError('Salvataggio del profilo incompleto')
            meta = dict(meta, slots=slots.get('s'))
            changed = inventory[ids[0]]['last_changed']
            if datetime.fromisoformat(changed).tzinfo is None:
                raise ValueError('Ora attivazione profilo non valida')
            meta['activated_at'] = changed
            result[kind] = meta
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(KINDS.get(kind, 'Profilo') + ': configurazione incompleta o non valida') from exc
    return result


def provision(data, ws, root, save):
    """Idempotent upgrade. Does not touch week values or activation flags."""
    for ident, row in data.items():
        if not row.get('commit'):
            continue
        cal = row.setdefault('calendar', {})
        profiles = cal.setdefault('profiles', {})
        for kind in KINDS:
            ids = profiles.setdefault(kind, [])
            while len(ids) < 2:
                helper = ws.call('input_text/create', name=f'nm_p_{ident}_{kind}_{len(ids)}', max=255)
                ids.append('input_text.' + helper['id'])
                save(data, root)
        for field in ('index', 'today', 'next', 'target'):
            if field not in cal:
                helper = ws.call('input_text/create', name=f'NM {field} {row["commit"]}', max=255)
                cal[field] = 'input_text.' + helper['id']
                save(data, root)
        encoded = json.dumps(profiles, separators=(',', ':'))
        if len(encoded) > 255:
            raise ValueError('Identificativi profili troppo lunghi')
        ws.call('call_service', domain='input_text', service='set_value', target={'entity_id': cal['index']}, service_data={'value': encoded})
        target = json.dumps({'e': row['entity'], 'p': row['project']}, separators=(',', ':'))
        if len(target) > 255:
            raise ValueError('Identificativo dispositivo troppo lungo')
        ws.call('call_service', domain='input_text', service='set_value', target={'entity_id': cal['target']}, service_data={'value': target})


def publish_preview(record, config, now, ws, states, occurrences):
    cal = record.get('calendar_helpers')
    if not cal:
        return
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(config['time_zone'])
    today = now.astimezone(zone).date()
    upcoming = occurrences(record['triggers'], config, now, horizon=32)
    rows = [[instant.astimezone(zone).strftime('%H:%M'), trigger['display_value']]
            for instant, trigger, _ in upcoming if instant.astimezone(zone).date() == today]
    future = next(((instant, trigger) for instant, trigger, _ in upcoming if instant > now), None)
    if record.get('warning'):
        rows=[]
    status = {'day': today.isoformat(), 'profile': selected_profile(record.get('calendar', {}), today),
              'mode': 'blocked' if record.get('warning') else 'active' if record['enabled'] else 'paused',
              'checked': now.replace(second=0, microsecond=0).isoformat()}
    if future:
        status.update(at=future[0].isoformat(), value=future[1]['display_value'])
    if record.get('warning'):
        status['why'] = record['warning'][:55]
        status.pop('at', None)
        status.pop('value', None)
    for entity, value in ((cal['today'], rows), (cal['next'], status)):
        encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        if len(encoded) > 255:
            # Solar shifts across midnight can exceed a single day's 8 slots.
            encoded = json.dumps({'overflow': True}) if entity == cal['today'] else json.dumps({'mode': 'blocked', 'why': 'Anteprima troppo lunga'})
        old = next((s['state'] for s in states if s['entity_id'] == entity), None)
        if old != encoded:
            ws.call('call_service', domain='input_text', service='set_value', target={'entity_id': entity}, service_data={'value': encoded})
