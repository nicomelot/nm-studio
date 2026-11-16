"""Project-bound scenes and schedules. Only explicit, allowlisted HA services.

The worker runs in the add-on, never in a browser. Schedule occurrences are
durably claimed before any service call: ambiguous sends are not retried.
"""
import copy
try:
    from .climate_cards import records as climate_card_records, upgrade as upgrade_cards
    from .schedule_calendar import selected_profile, publish_preview
    from .control_network import readings as network_readings
    from .control_buttons import ControlButtons
    from .control_features import ControlFeatures
    from .control_ha import HomeAssistantWidgets, actions as ha_actions, ATTRIBUTES as HA_ATTRIBUTES, plan as ha_plan, clean_value as ha_clean_value
    from .control_decisions import ControlDecisions, simulated, review_summary
    from .intelligence import summarize
except ImportError:
    from climate_cards import records as climate_card_records, upgrade as upgrade_cards
    from schedule_calendar import selected_profile, publish_preview
    from control_network import readings as network_readings
    from control_buttons import ControlButtons
    from control_features import ControlFeatures
    from control_ha import HomeAssistantWidgets, actions as ha_actions, ATTRIBUTES as HA_ATTRIBUTES, plan as ha_plan, clean_value as ha_clean_value
    from control_decisions import ControlDecisions, simulated, review_summary
    from intelligence import summarize
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .dashboard_publisher import HAWebSocket
    from .widget_layout import read_layout, save_layout, LAYOUT_LOCK
    from .installation_review import compare
except ImportError:
    from dashboard_publisher import HAWebSocket
    from widget_layout import read_layout, save_layout, LAYOUT_LOCK
    from installation_review import compare

UTC = timezone.utc
LOG = logging.getLogger('nm_control')
IDENT = re.compile(r'^[a-zA-Z0-9_-]{1,80}$')
ENTITY = re.compile(r'^(light|switch|cover|climate|scene)\.[a-z0-9_]+$')
ACTIONS = {'light': ['on', 'off'], 'dimmer': ['on', 'off', 'brightness'],
           'cover': ['open', 'stop', 'close', 'position'],
           'climate': ['temperature', 'hvac_mode']}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def binding(widget):
    # Renaming/moving a function keeps its identity; changing wiring invalidates it.
    return digest({k: widget.get(k) for k in ('type', 'entity_id', 'fields', 'command_mode')})


def catalog(layout, states, temperature_unit='°C'):
    by_entity = {s['entity_id']: s for s in states}
    result = []
    for i, w in enumerate(layout.get('widgets', [])):
        state = by_entity.get(w.get('entity_id'), {})
        attrs = state.get('attributes') or {}
        if w['type']=='climate':
            attrs={**attrs,'temperature_unit':attrs.get('temperature_unit') or temperature_unit}
        result.append({'id': binding(w), 'index': i, 'name': w['name'], 'room': w['room'],
                       'type': w['type'], 'entity_id': w.get('entity_id', ''),
                       'visible': w.get('visible', True), 'fields': w['fields'],
                       'ha_actions': ha_actions(state) if w['type']=='homeassistant' else [],
                       'actions': ha_actions(state) if w['type']=='homeassistant' else ['off'] if w.get('command_mode') == 'off_only' else ACTIONS.get(w['type'], []),
                       'state': state.get('state', 'unavailable'),
                       'attributes': {k: attrs[k] for k in ('brightness', 'current_position', 'current_temperature',
                           'temperature', 'min_temp', 'max_temp', 'temperature_unit', 'hvac_modes', 'hvac_action', 'unit_of_measurement', 'device_class', *HA_ATTRIBUTES) if k in attrs}})
    return result


def numeric(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Valore richiesto tra {low} e {high}')
    return value


def lab_candidates(layout, states):
    project = layout.get('project', '')
    if not project:
        return []
    prefix = 'nm_lab_' + project[:12] + '_'
    return [{'entity_id': s['entity_id'], 'name': (s.get('attributes') or {}).get('friendly_name', s['entity_id']),
             'state': s.get('state', 'unavailable')}
            for s in states if s['entity_id'].split('.')[0] in ('light', 'cover', 'climate')
            and s['entity_id'].split('.', 1)[1].startswith(prefix)]


def clean_actions(raw, layout):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise ValueError('Servono da 1 a 50 azioni')
    clean, targets = [], set()
    for a in raw:
        if not isinstance(a, dict):
            raise ValueError('Azione non valida')
        matches = [w for w in layout.get('widgets', []) if binding(w) == a.get('device')]
        if len(matches) != 1:
            raise ValueError('Dispositivo cambiato, mancante o duplicato: aggiorna il progetto')
        w = matches[0]
        entity = w.get('entity_id', '')
        if not ENTITY.fullmatch(entity) and not (w['type']=='homeassistant' and re.fullmatch(r'(light|switch|input_boolean|button|input_button|media_player)\.[a-z0-9_]+', entity)):
            raise ValueError('Associa prima il dispositivo a una entità Home Assistant')
        # Multiple actions for the same climate are valid (mode then setpoint).
        key = (entity, a.get('action'))
        if key in targets:
            raise ValueError('Azione duplicata per lo stesso dispositivo')
        targets.add(key)
        action, value = a.get('action'), a.get('value')
        if w['type'] == 'homeassistant':
            clean.append({'device': binding(w), 'action': action, 'value': ha_clean_value(entity, action, value)})
            continue
        if action not in ACTIONS.get(w['type'], []):
            raise ValueError('Azione incompatibile con il dispositivo')
        if w.get('command_mode') == 'off_only' and action != 'off':
            raise ValueError('Il dispositivo consente solo lo spegnimento')
        if action in ('brightness', 'position'):
            numeric(value, 0, 100)
            if type(value) is not int:
                raise ValueError('La percentuale deve essere intera')
        elif action == 'temperature':
            numeric(value, -50, 100)
        elif action == 'hvac_mode':
            if value not in ('off', 'heat', 'cool', 'heat_cool', 'auto', 'dry', 'fan_only'):
                raise ValueError('Modalità termostato non valida')
        else:
            value = None
        clean.append({'device': binding(w), 'action': action, 'value': value})
    return clean


def clean_triggers(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 64:
        raise ValueError('Servono da 1 a 64 fasce orarie')
    clean, ids, occurrences_seen = [], set(), set()
    for t in raw:
        if not isinstance(t, dict) or not IDENT.fullmatch(str(t.get('id', ''))) or t['id'] in ids:
            raise ValueError('Identità fascia non valida')
        ids.add(t['id'])
        days = t.get('days')
        if not isinstance(days, list) or not days or any(type(d) is not int or d not in range(7) for d in days):
            raise ValueError('Seleziona almeno un giorno della settimana')
        kind = t.get('kind')
        row = {'id': t['id'], 'days': sorted(set(days)), 'kind': kind}
        if kind == 'time':
            if not isinstance(t.get('time'), str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t['time']):
                raise ValueError('Orario non valido')
            row['time'] = t['time']
        elif kind in ('sunrise', 'sunset'):
            offset = t.get('offset', 0)
            if type(offset) is not int or not -180 <= offset <= 180:
                raise ValueError('Scostamento solare richiesto tra -180 e 180 minuti')
            row['offset'] = offset
        else:
            raise ValueError('Tipo di orario non valido')
        # Optional per-slot values allow a single weekly thermostat programme.
        if 'value' in t:
            row['value'] = t['value']
        for day in row['days']:
            occurrence = (day, kind, row.get('time'), row.get('offset'))
            if occurrence in occurrences_seen:
                raise ValueError('Due fasce coincidono nello stesso giorno: uniscile o cambia orario')
            occurrences_seen.add(occurrence)
        clean.append(row)
    return clean


def slot_actions(record, trigger=None):
    if record.get('source')=='ha_card' and trigger and trigger['id'] in record.get('slot_actions',{}):
        return copy.deepcopy(record['slot_actions'][trigger['id']])
    actions = copy.deepcopy(record['actions'])
    if trigger and 'value' in trigger:
        if len(actions) != 1 or actions[0]['action'] not in ('temperature', 'brightness', 'position', 'volume'):
            raise ValueError('Un valore per fascia richiede una singola azione numerica')
        actions[0]['value'] = trigger['value']
    return actions


def occurrences(triggers, config, now, horizon=8):
    """UTC instants; skip nonexistent DST times, choose first fall-back occurrence.

    Weekdays refer to the solar event's local date, before applying the offset.
    Astronomical absence (polar day/night) simply produces no event for that date.
    """
    zone = ZoneInfo(config['time_zone'])
    today = now.astimezone(zone).date()
    result = []
    for day_offset in range(-1, horizon):
        date = today + timedelta(days=day_offset)
        for t in triggers:
            if 'calendar' in t and selected_profile(t['calendar'],date)!=t['profile']:
                continue
            if date.weekday() not in t['days']:
                continue
            if t['kind'] == 'time':
                hour, minute = map(int, t['time'].split(':'))
                local = datetime(date.year, date.month, date.day, hour, minute, tzinfo=zone, fold=0)
                instant = local.astimezone(UTC)
                if instant.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                    continue
            else:
                from astral import Observer
                from astral.sun import sunrise, sunset
                observer = Observer(numeric(config['latitude'], -90, 90), numeric(config['longitude'], -180, 180),
                                    numeric(config.get('elevation', 0), -500, 10000))
                try:
                    instant = (sunrise if t['kind'] == 'sunrise' else sunset)(observer, date=date, tzinfo=zone).astimezone(UTC)
                except ValueError:
                    continue
                instant += timedelta(minutes=t['offset'])
            result.append((instant, t, f"{t['id']}:{date.isoformat()}"))
    return sorted(result, key=lambda item: item[0])


def service_plan(layout, actions, ws, states=None):
    """Validate EVERY action before sending any. Never accept arbitrary services."""
    actions = clean_actions(actions, layout)
    states = ws.call('get_states') if states is None else states
    if not isinstance(states, list):
        raise ValueError('Stati Home Assistant non disponibili')
    by_entity = {s['entity_id']: s for s in states}
    calls = []
    for a in actions:
        index, w = next((i, w) for i, w in enumerate(layout['widgets']) if binding(w) == a['device'])
        ident, kind, action = w['entity_id'], w['type'], a['action']
        if kind == 'homeassistant':
            calls.append(ha_plan(w, action, a['value'], states)[0])
            continue
        domain = ident.split('.')[0]
        expected = {'light': {'light', 'switch'}, 'dimmer': {'light'}, 'cover': {'cover'}, 'climate': {'climate'}}[kind]
        if domain not in expected:
            raise ValueError('Entità HA incompatibile con il dispositivo')
        state = by_entity.get(ident)
        if not state or (state.get('state') in ('unknown', 'unavailable') and action != 'stop'):
            raise ValueError(w['name'] + ': stato non disponibile')
        # Preserve existing KNX alignment gate for real KNX light/cover functions.
        if kind in ('light', 'dimmer', 'cover') and '.nm_lab_' not in ident and domain != 'switch':
            if compare(layout, index, ws)['status'] != 'present':
                raise ValueError(w['name'] + ': verifica associazione KNX nel collaudo')
        attrs = state.get('attributes') or {}
        data = {}
        if action in ('on', 'off'):
            service = 'turn_' + action
        elif action == 'brightness':
            if not set(attrs.get('supported_color_modes') or []) - {'onoff', 'unknown'}:
                raise ValueError('Regolazione luminosità non supportata')
            service, data = 'turn_on', {'brightness_pct': a['value']}
        elif action in ('open', 'stop', 'close', 'position'):
            feature = {'open': 1, 'close': 2, 'position': 4, 'stop': 8}[action]
            if type(attrs.get('supported_features')) is not int or not attrs['supported_features'] & feature:
                raise ValueError('Comando tapparella non supportato')
            service = {'open': 'open_cover', 'close': 'close_cover', 'stop': 'stop_cover', 'position': 'set_cover_position'}[action]
            if action == 'position':
                data['position'] = a['value']
        elif action == 'temperature':
            if type(attrs.get('supported_features')) is not int or not attrs['supported_features'] & 1:
                raise ValueError('Il termostato non supporta un setpoint singolo')
            numeric(a['value'], attrs.get('min_temp', 7), attrs.get('max_temp', 35))
            service, data = 'set_temperature', {'temperature': a['value']}
        else:
            if a['value'] not in attrs.get('hvac_modes', []):
                raise ValueError('Modalità non supportata dal termostato')
            service, data = 'set_hvac_mode', {'hvac_mode': a['value']}
        calls.append({'domain': domain, 'service': service, 'target': {'entity_id': ident}, 'service_data': data})
    return calls


class ControlEngine:
    def __init__(self, root, layout_provider=read_layout, connection_factory=HAWebSocket):
        self.root = Path(root)
        self.path = self.root / 'nm_control_automations.json'
        self.journal = self.root / 'nm_control_runs.sqlite'
        self.layout_provider = layout_provider
        self.connection_factory = connection_factory
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker = None
        self.features = ControlFeatures(self, binding)
        self.decisions = ControlDecisions(self)
        self.ha_widgets = HomeAssistantWidgets(self, binding)
        self.buttons = ControlButtons(self)
        self.health = {'running': False, 'last_check': None, 'error': None}

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'revision': 0, 'projects': {}}
        if self.path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Archivio automazioni troppo grande')
        raw = json.loads(self.path.read_text(encoding='utf-8'))
        if raw.get('version') != 1 or not isinstance(raw.get('projects'), dict):
            raise ValueError('Archivio automazioni non valido')
        return raw

    def write(self, raw):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=self.root, encoding='utf-8', delete=False) as f:
                tmp = f.name
                json.dump(raw, f, ensure_ascii=False, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    def records(self, raw, project):
        return raw['projects'].get(project, [])

    def combined(self, layout, raw):
        return {**layout, 'widgets': layout.get('widgets', []) + self.features.widgets(layout.get('project', ''), raw)}

    def snapshot(self):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            states, config, error = [], {}, None
            try:
                with self.connection_factory() as ws:
                    states, config = ws.call('get_states'), ws.call('get_config')
            except Exception as exc:
                error = 'Home Assistant non disponibile: ' + str(exc)[:160]
            records = copy.deepcopy(self.records(raw, layout.get('project', '')))
            records += climate_card_records(self.root,self.combined(layout,raw),states,binding)
            current = datetime.now(UTC)
            for r in records:
                r['next_runs'], r['warning'] = [], r.get('warning')
                try:
                    clean_actions(r['actions'], self.combined(layout, raw))
                    if r['kind'] == 'schedule':
                        # Card calendars validate each profile independently;
                        # equal times in mutually exclusive profiles are valid.
                        if r.get('source')!='ha_card':clean_triggers(r['triggers'])
                        r['next_runs'] = [d.isoformat() for d, _, _ in occurrences(r['triggers'], config, current) if d >= current][:8]
                        if not r['next_runs']:
                            r['warning'] = 'Nessuna occorrenza nei prossimi 8 giorni'
                except (ValueError, KeyError, TypeError) as exc:
                    r['warning'] = str(exc)
            combined = {**layout, 'widgets':layout.get('widgets', []) + self.features.widgets(layout.get('project',''),raw)}
            return {'project': layout.get('project', ''), 'fingerprint': digest(layout), 'revision': raw['revision'],
                    'rooms': list(dict.fromkeys(layout.get('rooms', []) + [w['room'] for w in combined['widgets']])),
                    'devices': catalog(combined, states, config.get('unit_system', {}).get('temperature') or '°C'), 'widget_candidates': self.features.candidates(states), 'release_error':self.features.last_release_error, 'lab_candidates': lab_candidates(layout, states),
                    'network_states': network_readings(states),
                    'decision_model': review_summary(states),
                    'decision_devices': [binding(w) for w in layout.get('widgets', []) if simulated(w.get('entity_id'), layout.get('project',''))],
                    'button_links': [{**r, 'active': r in self.buttons.active(layout, raw)} for r in self.buttons.rules(raw, layout.get('project',''))],
                    'button_listener': copy.deepcopy(self.buttons.health),
                    'records': records, 'logs': self.history(layout.get('project', '')),
                    'ha_error': error, 'time_zone': config.get('time_zone'),
                    'location_name': config.get('location_name'),
                    'temperature_unit': config.get('unit_system', {}).get('temperature'),
                    'scheduler': copy.deepcopy(self.health)}

    def guard(self, payload, layout, raw):
        if not isinstance(payload, dict) or payload.get('confirm') is not True:
            raise ValueError('Conferma esplicita richiesta')
        if not layout.get('project') or payload.get('project') != layout['project'] or payload.get('fingerprint') != digest(layout):
            raise ValueError('Progetto cambiato: aggiorna la pagina')
        if payload.get('revision') != raw['revision']:
            raise ValueError('Automazioni cambiate in un’altra sessione: aggiorna')

    def save(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            record = payload.get('record')
            if not isinstance(record, dict):
                raise ValueError('Configurazione non valida')
            ident = record.get('id') or str(uuid.uuid4())
            if str(ident).startswith('haweek_'):raise ValueError('Modifica la settimana dalla card Home Assistant')
            name, kind = record.get('name'), record.get('kind')
            if not IDENT.fullmatch(ident) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or kind not in ('scene', 'schedule'):
                raise ValueError('Nome o tipo non valido')
            records = raw['projects'].setdefault(layout['project'], [])
            old = next((r for r in records if r['id'] == ident), None)
            if not old and len(records) >= 200:
                raise ValueError('Limite di 200 automazioni per progetto')
            room = record.get('room', '')
            if not isinstance(room, str) or len(room) > 240:
                raise ValueError('Ambiente non valido')
            clean = {'id': ident, 'name': name.strip(), 'kind': kind, 'room': room,
                     'actions': clean_actions(record.get('actions'), layout), 'enabled': False,
                     'triggers': clean_triggers(record.get('triggers')) if kind == 'schedule' else []}
            for t in clean['triggers']:
                clean_actions(slot_actions(clean, t), layout)
            # Every edit pauses the schedule. Activation is a separate reviewed step.
            clean['updated_at'] = datetime.now(UTC).isoformat()
            raw['projects'][layout['project']] = [r for r in records if r['id'] != ident] + [clean]
            raw['revision'] += 1
            self.write(raw)
            return {'saved': True, 'id': ident, 'enabled': False}

    def copy_week(self, payload):
        """Validate all destinations, then persist independent paused copies atomically."""
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            records = self.records(raw, layout['project'])
            source = next((r for r in records if r['id'] == payload.get('id')), None)
            if not source or source['kind'] != 'schedule' or len(source['actions']) != 1 or source['actions'][0]['action'] != 'temperature':
                raise ValueError('Scegli un programma di temperatura di un singolo termostato')
            clean_actions(source['actions'], layout)
            triggers = clean_triggers(source['triggers'])
            targets = payload.get('targets')
            if not isinstance(targets, list) or not 1 <= len(targets) <= 50 or any(not isinstance(t, str) for t in targets) or len(set(targets)) != len(targets):
                raise ValueError('Scegli da 1 a 50 termostati diversi')
            if len(records) + len(targets) > 200:
                raise ValueError('Limite di 200 automazioni per progetto')
            copies, summaries = [], []
            used_entities = {w['entity_id'] for w in layout['widgets'] if binding(w) == source['actions'][0]['device']}
            with self.connection_factory() as ws:
                states = ws.call('get_states')
                for target in targets:
                    matches = [w for w in layout['widgets'] if binding(w) == target and w['type'] == 'climate']
                    if len(matches) != 1 or target == source['actions'][0]['device']:
                        raise ValueError('Destinatario non valido o uguale al termostato di origine')
                    widget = matches[0]
                    if widget['entity_id'] in used_entities:
                        raise ValueError('Entità di destinazione duplicata o uguale all’origine')
                    used_entities.add(widget['entity_id'])
                    ident = 'copy_' + digest({'source':source['id'], 'target':target})[:40]
                    if any(r['id'] == ident for r in records):
                        raise ValueError(widget['name'] + ': copia già presente; modifica il programma esistente')
                    record = {'id':ident, 'name':(source['name'][:38] + ' · ' + widget['name'][:39])[:80],
                              'kind':'schedule', 'room':widget.get('room',''), 'enabled':False,
                              'actions':[dict(source['actions'][0], device=target)], 'triggers':copy.deepcopy(triggers)}
                    clean_actions(record['actions'], layout)
                    service_plan(layout, record['actions'], ws, states)
                    for trigger in triggers:
                        actions = clean_actions(slot_actions(record, trigger), layout)
                        service_plan(layout, actions, ws, states)
                    copies.append(record)
                    summaries.append({'id':ident, 'name':widget['name'], 'room':widget.get('room',''),
                                      'existing':sum(r['kind']=='schedule' and any(a['device']==target for a in r['actions']) for r in records)})
            proof = digest({'copies':copies, 'layout':layout, 'revision':raw['revision']})
            if payload.get('preview_hash') is None:
                return {'preview_hash':proof, 'targets':summaries, 'triggers':triggers}
            if payload['preview_hash'] != proof:
                raise ValueError('Anteprima cambiata: verifica di nuovo i destinatari')
            for record in copies:
                record['updated_at'] = datetime.now(UTC).isoformat()
            raw['projects'][layout['project']] = records + copies
            raw['revision'] += 1
            self.write(raw)
            return {'saved':True, 'count':len(copies), 'ids':[r['id'] for r in copies]}

    def preview(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            record = next((r for r in self.records(raw, layout['project']) if r['id'] == payload.get('id')), None)
            if record is None:
                raise ValueError('Scenario o programma non trovato')
            with self.connection_factory() as ws:
                config = ws.call('get_config')
                calls = service_plan(layout, record['actions'], ws)
                for t in record['triggers']:
                    service_plan(layout, slot_actions(record, t), ws)
                upcoming = [d.isoformat() for d, _, _ in occurrences(record['triggers'], config, datetime.now(UTC)) if d >= datetime.now(UTC)][:8] if record['kind'] == 'schedule' else []
                if record['kind'] == 'schedule' and not upcoming:
                    raise ValueError('Nessuna occorrenza solare/oraria nei prossimi 8 giorni')
                if record['kind'] == 'schedule':
                    self.check_conflicts(record, self.records(raw, layout['project']), config)
            return {'calls': calls, 'next_runs': upcoming, 'time_zone': config.get('time_zone'),
                    'preview_hash': digest({'layout': layout, 'record': record, 'revision': raw['revision']}),
                    'note': 'Comandi reali tramite HA; l’accettazione non conferma il risultato fisico.'}

    def check_conflicts(self, record, records, config):
        """Reject different commands for one binding at coincident upcoming instants."""
        now = datetime.now(UTC)
        def commands(r):
            for instant, trigger, _ in occurrences(r['triggers'], config, now):
                if instant < now:
                    continue
                for action in slot_actions(r, trigger):
                    group = {'on': 'power', 'off': 'power', 'brightness': 'power',
                             'open': 'motion', 'close': 'motion', 'stop': 'motion', 'position': 'motion'}.get(action['action'], action['action'])
                    yield (instant.replace(microsecond=0), action['device'], group), (action['action'], action['value'])
        proposed = {}
        for key, value in commands(record):
            if key in proposed and proposed[key] != value:
                raise ValueError('Due fasce del programma inviano comandi diversi nello stesso istante')
            proposed[key] = value
        for other in records:
            if other['id'] == record['id'] or other['kind'] != 'schedule' or not other.get('enabled'):
                continue
            for key, value in commands(other):
                if key in proposed and proposed[key] != value:
                    raise ValueError('Conflitto con il programma attivo: ' + other['name'])

    def activate(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            record = next((r for r in self.records(raw, layout['project']) if r['id'] == payload.get('id')), None)
            if not record or record['kind'] != 'schedule' or type(payload.get('enabled')) is not bool:
                raise ValueError('Programmazione non valida')
            if payload['enabled']:
                check = self.preview(payload)
                if check['preview_hash'] != payload.get('preview_hash'):
                    raise ValueError('Rivedi l’anteprima prima di attivare')
                record['activated_at'] = datetime.now(UTC).isoformat()
            record['enabled'] = payload['enabled']
            raw['revision'] += 1
            self.write(raw)
            return {'enabled': record['enabled']}

    @contextmanager
    def db(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.journal, timeout=10)
        db.execute('CREATE TABLE IF NOT EXISTS holds (token TEXT PRIMARY KEY, project TEXT, device TEXT, entity TEXT, expires REAL, created REAL, status TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS runs (key TEXT PRIMARY KEY, project TEXT, name TEXT, time TEXT, status TEXT, detail TEXT)')
        try:
            with db:
                yield db
        finally:
            db.close()

    def action_preview(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            actions = clean_actions(payload.get('actions'), layout)
            with self.connection_factory() as ws:
                calls = service_plan(layout, actions, ws)
            return {'calls': calls, 'preview_hash': digest({'layout': layout, 'actions': actions}),
                    'note': 'Invio di comandi reali: verifica il dispositivo dopo l’esecuzione.'}

    def action_run(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            actions = clean_actions(payload.get('actions'), layout)
            if payload.get('preview_hash') != digest({'layout': layout, 'actions': actions}):
                raise ValueError('Rivedi l’anteprima del comando')
            request = payload.get('request_id', '')
            if not isinstance(request, str) or not IDENT.fullmatch(request):
                raise ValueError('Identità esecuzione richiesta')
            return self.execute(layout, {'name': 'Comando manuale'}, actions, f"manual:{layout['project']}:{request}")

    def history(self, project):
        if not self.journal.exists():
            return []
        with self.db() as db:
            rows = db.execute('SELECT name,time,status,detail FROM runs WHERE project=? ORDER BY rowid DESC LIMIT 100', (project,)).fetchall()
        return [dict(zip(('name', 'time', 'status', 'detail'), row)) for row in rows]

    def execute(self, layout, record, actions, key, planner=service_plan):
        with self.db() as db:
            try:
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)', (key, layout['project'], record['name'], datetime.now(UTC).isoformat(), 'in_progress', 'Invio iniziato; esito non ancora confermato'))
            except sqlite3.IntegrityError:
                return {'duplicate': True}
        sent = 0
        try:
            with self.connection_factory() as ws:
                calls = planner(layout, actions, ws)
                for call in calls:
                    ws.call('call_service', **call)
                    sent += 1
            status, detail = 'accepted', f'{sent} comandi accettati da HA; verifica gli stati fisici'
        except Exception as exc:
            status, detail = 'error', f'{sent} comandi accettati prima dell’errore. Esito del comando fallito non confermato; nessun reinvio automatico. {str(exc)[:180]}'
        with self.db() as db:
            db.execute('UPDATE runs SET status=?,detail=? WHERE key=?', (status, detail, key))
            db.execute("DELETE FROM runs WHERE time < ?", ((datetime.now(UTC) - timedelta(days=90)).isoformat(),))
        return {'status': status, 'message': detail, 'sent': sent}

    def run(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            layout = self.combined(layout, raw)
            record = next((r for r in self.records(raw, layout['project']) if r['id'] == payload.get('id')), None)
            if not record or record['kind'] != 'scene':
                raise ValueError('Scenario non trovato')
            if payload.get('preview_hash') != digest({'layout': layout, 'record': record, 'revision': raw['revision']}):
                raise ValueError('Anteprima cambiata: verifica nuovamente')
            request = payload.get('request_id', '')
            if not isinstance(request, str) or not IDENT.fullmatch(request):
                raise ValueError('Identità esecuzione richiesta')
            return self.execute(layout, record, record['actions'], f"manual:{layout['project']}:{request}")

    def add_lab(self, payload):
        """Append selected existing virtual entities; never replace real bindings."""
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            selected = payload.get('entities')
            if not isinstance(selected, list) or not 1 <= len(selected) <= 50:
                raise ValueError('Seleziona da 1 a 50 simulazioni')
            with self.connection_factory() as ws:
                states = ws.call('get_states')
            allowed = {s['entity_id'] for s in lab_candidates(layout, states)}
            by_id = {s['entity_id']: s for s in states}
            linked = {w.get('entity_id') for w in layout['widgets']}
            additions = []
            for item in selected:
                if not isinstance(item, dict) or item.get('entity_id') not in allowed:
                    raise ValueError('Sono ammesse solo simulazioni NM LAB del progetto attivo')
                ident, name = item['entity_id'], item.get('name')
                if ident in linked:
                    raise ValueError('Simulazione già associata o selezionata due volte')
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 70:
                    raise ValueError('Inserisci un nome per ogni simulazione')
                if by_id[ident].get('state') in ('unknown', 'unavailable'):
                    raise ValueError('Simulazione non disponibile')
                kind = ident.split('.')[0]
                if kind == 'light' and set(by_id[ident].get('attributes', {}).get('supported_color_modes') or []) - {'onoff', 'unknown'}:
                    kind = 'dimmer'
                additions.append({'type': kind, 'name': 'SIM · ' + name.strip(), 'room': 'Collaudo simulato',
                                  'fields': {}, 'entity_id': ident})
                linked.add(ident)
            layout['widgets'].extend(additions)
            layout['rooms'] = list(dict.fromkeys(layout.get('rooms', []) + ['Collaudo simulato']))
            return save_layout({**layout, 'confirm': True})

    def assign(self, payload):
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            self.guard(payload, layout, raw)
            room = payload.get('room')
            if not isinstance(room, str) or not 1 <= len(room.strip()) <= 240:
                raise ValueError('Nome ambiente non valido')
            room = room.strip()
            ids = payload.get('devices', [])
            if not isinstance(ids, list) or len(ids) > 200 or any(not isinstance(i, str) for i in ids):
                raise ValueError('Selezione dispositivi non valida')
            for ident in ids:
                matches = [w for w in layout['widgets'] if binding(w) == ident]
                if len(matches) != 1:
                    raise ValueError('Dispositivo mancante o duplicato')
                matches[0]['room'] = room
            layout['rooms'] = list(dict.fromkeys(layout.get('rooms', []) + [room]))
            return save_layout({**layout, 'confirm': True})

    def tick(self, now=None):
        now = now or datetime.now(UTC)
        with LAYOUT_LOCK, self.lock:
            layout, raw = self.layout_provider(), self.read()
            layout = self.combined(layout, raw)
            active = [r for r in self.records(raw, layout.get('project', '')) if r.get('enabled') and r['kind'] == 'schedule']
            with self.connection_factory() as ws:
                states=ws.call('get_states')
                card_records=climate_card_records(self.root,layout,states,binding)
                config = ws.call('get_config') if card_records else None
                for record in card_records:
                    conflicts=[r for r in active if any(a['device']==record['actions'][0]['device'] for a in r['actions'])]
                    if conflicts:
                        record['enabled']=False;record['warning']='Sospesa: altro programma NM attivo sul dispositivo'
                    message=record.get('warning') or ('Ultimo controllo: attiva' if record['enabled'] else 'Ultimo controllo: in pausa')
                    if record.get('status_entity'):
                        old=next((s for s in states if s['entity_id']==record['status_entity']),None)
                        if old and old.get('state')!=message:ws.call('call_service',domain='input_text',service='set_value',target={'entity_id':record['status_entity']},service_data={'value':message[:255]})
                    publish_preview(record,config,now,ws,states,occurrences)
                active += [r for r in card_records if r['enabled']]
                if not active:return
                config = ws.call('get_config')
            for r in active:
                for instant, trigger, occurrence in occurrences(r['triggers'], config, now, horizon=2):
                    if 0 <= (now - instant).total_seconds() <= 60 and instant >= max(datetime.fromisoformat(r['activated_at']),datetime.fromisoformat(trigger.get('not_before',r['activated_at']))):
                        self.execute(layout, r, slot_actions(r, trigger), f"scheduled:{layout['project']}:{r['id']}:{occurrence}")

    def start(self):
        self.features.start()
        self.buttons.start()
        if self.worker and self.worker.is_alive():
            return
        def loop():
            self.health['running'] = True
            upgraded=False
            while not self.stop_event.is_set():
                try:
                    if not upgraded:
                        with self.connection_factory() as ws:upgrade_cards(ws,self.root)
                        upgraded=True
                    self.tick()
                    self.health.update(last_check=datetime.now(UTC).isoformat(), error=None)
                except Exception as exc:
                    self.health.update(error=str(exc)[:180])
                    LOG.warning('Schedule tick failed: %s', type(exc).__name__)
                self.stop_event.wait(10)
            self.health['running'] = False
        self.worker = threading.Thread(target=loop, name='nm-schedules', daemon=True)
        self.worker.start()
