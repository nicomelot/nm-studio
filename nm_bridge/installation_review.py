"""Unified, read-only comparison and explicitly approved additive KNX updates."""
from copy import deepcopy

try:
    from .dashboard_publisher import HAWebSocket
    from .missing_ha_generator import fingerprint
    from .knx_entity_plan import build
    from .knx_install import install_step
    from .widget_layout import read_layout, LAYOUT_LOCK
except ImportError:
    from dashboard_publisher import HAWebSocket
    from missing_ha_generator import fingerprint
    from knx_entity_plan import build
    from knx_install import install_step
    from widget_layout import read_layout, LAYOUT_LOCK


def desired(layout, index):
    draft = deepcopy(layout)
    w = draft['widgets'][index]
    w.pop('entity_id', None)
    review = {'source_fingerprint': fingerprint(draft), 'devices': [
        {'index': index, 'name': w['name'], 'fields': w['fields'], 'approved': True}]}
    return build(draft, review)['calls'][0]


def compare(layout, index, ws):
    w = layout['widgets'][index]
    row = {**deepcopy(w), 'index': index, 'status': 'review', 'reason': ''}
    try:
        target = desired(layout, index)
        ident = w.get('entity_id')
        if not ident:
            used = ws.call('knx/get_entities_by_group')
            if not isinstance(used, dict):
                raise ValueError('Inventario indirizzi KNX non verificabile')
            addresses = {v for g in target['data']['knx'].values() if isinstance(g, dict)
                         for k, v in g.items() if k in ('write', 'state') and isinstance(v, str)}
            if addresses.intersection(used):
                raise ValueError('GA già configurati in HA: associa l’entità esistente')
            if sum(x.get('fields', {}).get('command') == w['fields'].get('command') for x in layout['widgets']) > 1:
                raise ValueError('Comando presente in più funzioni: verifica i duplicati')
            row.update(status='create', reason='Pronta da creare')
            return row
        current = ws.call('knx/get_entity_config', entity_id=ident)
        if not isinstance(current, dict) or current.get('platform') != target['platform']:
            raise ValueError('Entità non compatibile con la funzione KNX')
        data = current.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('knx'), dict) or not isinstance(data.get('entity'), dict):
            raise ValueError('Configurazione KNX non verificabile')
        merged = deepcopy(data)
        changes = []
        primary = {'cover': 'ga_up_down', 'button': 'ga_send'}.get(target['platform'], 'ga_switch')
        if (data['knx'].get(primary) or {}).get('write') != w['fields'].get('command'):
            raise ValueError('Il comando principale HA non coincide: verifica l’associazione')
        used = ws.call('knx/get_entities_by_group')
        if not isinstance(used, dict):
            raise ValueError('Inventario indirizzi KNX non verificabile')
        current_ga = {v for g in data['knx'].values() if isinstance(g, dict)
                      for k, v in g.items() if k in ('write', 'state') and isinstance(v, str)}
        # Keep HA name, device, options and all configured GA; fill empty roles only.
        for group, roles in target['data']['knx'].items():
            if group == 'data':
                if data['knx'].get(group) != roles:
                    raise ValueError('Valore del pulsante diverso in HA: verifica la configurazione KNX')
                continue
            existing = merged['knx'].get(group) or {}
            if not isinstance(existing, dict):
                raise ValueError('Formato indirizzi KNX non verificabile')
            existing = deepcopy(existing)
            for role, ga in roles.items():
                old = existing.get(role)
                if old and old != ga:
                    raise ValueError('Indirizzo diverso in HA: ' + group + '/' + role + '. Verifica manualmente.')
                if not old:
                    if ga in used and ga not in current_ga:
                        raise ValueError('Indirizzo già usato in HA: ' + ga)
                    existing[role] = ga
                    changes.append(group + '/' + role + ': ' + ga)
            merged['knx'][group] = existing
        row.update(status='update' if changes else 'present',
                   reason='Completa: ' + ', '.join(changes) if changes else 'Già presente e allineata',
                   current_fingerprint=fingerprint(current),
                   call={'type': 'knx/update_entity', 'platform': target['platform'], 'entity_id': ident, 'data': merged})
    except (ValueError, RuntimeError, KeyError, TypeError) as exc:
        row.update(status='review', reason='Da verificare: ' + str(exc)[:180])
    return row


def preview(layout, connection_factory=HAWebSocket):
    with connection_factory() as ws:
        devices = [compare(layout, i, ws) for i in range(len(layout.get('widgets', [])))]
    return {'project': layout.get('project'), 'source_fingerprint': fingerprint(layout), 'devices': devices}


def apply_one(payload, connection_factory=HAWebSocket):
    if not isinstance(payload, dict) or any(payload.get(k) is not True for k in ('confirm', 'ets_confirmed', 'backup_confirmed')):
        raise ValueError('Conferma, verifica ETS e backup richiesti')
    with LAYOUT_LOCK:
        layout = read_layout()
        if payload.get('source_fingerprint') != fingerprint(layout):
            raise ValueError('Configurazione cambiata: aggiorna il riepilogo')
        index = payload.get('index')
        if type(index) is not int or not 0 <= index < len(layout['widgets']):
            raise ValueError('Funzione non valida')
        with connection_factory() as ws:
            row = compare(layout, index, ws)
            expected = payload.get('expected')
            if row != expected or row['status'] not in ('create', 'update'):
                raise ValueError('Confronto cambiato: aggiorna il riepilogo prima di applicare')
            if row['status'] == 'update':
                base = ws.call('knx/get_base_data')
                call = row['call']
                if call['platform'] not in base.get('supported_platforms', []):
                    raise ValueError('Piattaforma KNX non disponibile')
                checked = ws.call('knx/validate_entity', platform=call['platform'], data=call['data'])
                if not isinstance(checked, dict) or checked.get('success') is not True:
                    raise ValueError('Validazione KNX rifiutata: nessun aggiornamento eseguito')
                if fingerprint(ws.call('knx/get_entity_config', entity_id=row['entity_id'])) != row['current_fingerprint']:
                    raise ValueError('Entità modificata durante il confronto: riprova')
                result = ws.call('knx/update_entity', **{k: v for k, v in call.items() if k != 'type'})
                if not isinstance(result, dict) or result.get('success') is not True:
                    raise ValueError('Aggiornamento non confermato: ricarica prima di riprovare')
                after = compare(layout, index, ws)
                if after['status'] != 'present':
                    raise ValueError('Aggiornamento inviato ma rilettura non allineata: verifica in HA')
                return {'entity_id': row['entity_id'], 'linked': True, 'updated': True,
                        'source_fingerprint': fingerprint(layout)}
        review = {'source_fingerprint': fingerprint(layout), 'devices': [
            {'index': index, 'name': row['name'], 'fields': row['fields'], 'approved': True}]}
        return install_step({**payload, 'review': review, 'call_index': 0,
                             'expected_call': build(layout, review)['calls'][0]})
