"""Optional presence simulation: selected project lights, read-only alarm gate.

One light at a time, only starting from off. Durable ownership prevents blind
restoration after manual changes; weekly programs are never rewritten.
"""
import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
try:
    from .widget_layout import LAYOUT_LOCK
except ImportError:
    from widget_layout import LAYOUT_LOCK


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def light_signature(state):
    return digest({k: state.get(k) for k in ('state', 'attributes', 'last_changed')})


def in_window(now, zone, start, end):
    value = now.astimezone(ZoneInfo(zone)).strftime('%H:%M')
    return start <= value < end if start < end else value >= start or value < end


class ControlPresence:
    def __init__(self, engine):
        self.e = engine
        self.path = engine.root / 'nm_presence_runtime.json'
        self.random = random.SystemRandom()
        self.recover = True
        self.error = None

    def runtime(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(value), encoding='utf-8')
        os.replace(temp, self.path)

    def candidates(self, layout, states):
        inventory = {s['entity_id']: s for s in states}
        result = {}
        for w in layout.get('widgets', []):
            entity = w.get('entity_id', '')
            if entity.startswith('light.') and w.get('type') in ('light', 'dimmer', 'homeassistant') and w.get('command_mode') != 'off_only':
                result[entity] = {'entity': entity, 'name': w['name'], 'state': inventory.get(entity, {}).get('state', 'unavailable')}
        return list(result.values())

    def conflicts(self, layout, raw, states):
        from importlib import import_module
        cards = import_module('.climate_cards', __package__) if __package__ else import_module('climate_cards')
        inventory = {s['entity_id']: s for s in states}
        blocked = set()
        for row in cards.read(self.e.root).values():
            try:
                if row['project'] == layout['project'] and json.loads(inventory[row['commit']]['state']).get('enabled'):
                    blocked.add(row['entity'])
            except (KeyError, ValueError, TypeError):
                pass
        from importlib import import_module as module
        engine = module('.control_engine', __package__) if __package__ else module('control_engine')
        bindings = {engine.binding(w): w.get('entity_id') for w in layout.get('widgets', [])}
        for record in self.e.records(raw, layout['project']):
            if record.get('enabled') and record.get('kind') == 'schedule':
                blocked.update(bindings.get(a['device']) for a in record.get('actions', []))
        return blocked

    def handle(self, payload):
        e = self.e
        with LAYOUT_LOCK, e.lock:
            original, raw = e.layout_provider(), e.read()
            e.guard(payload, original, raw)
            layout = e.combined(original, raw)
            operation = payload.get('operation', 'inspect')
            saved = raw.get('presence', {}).get(layout['project'], {})
            with e.connection_factory() as ws:
                states = ws.call('get_states')
                config = ws.call('get_config')
                if operation == 'sim_alarm':
                    entity = next((s['entity_id'] for s in states if s['entity_id'].startswith('input_boolean.nm_presence_sim_')), None)
                    if not entity:
                        helper = ws.call('input_boolean/create', name='nm_presence_sim_armed_away', icon='mdi:shield-home')
                        entity = 'input_boolean.' + helper['id']
                    return {'entity': entity}
            lights = self.candidates(layout, states)
            alarms = [{'entity': s['entity_id'], 'name': s.get('attributes', {}).get('friendly_name', s['entity_id']), 'simulated': s['entity_id'].startswith('input_boolean.nm_presence_sim_')}
                      for s in states if s['entity_id'].startswith(('alarm_control_panel.', 'input_boolean.nm_presence_sim_'))]
            if operation == 'inspect':
                runtime = self.runtime()
                return {'config': saved, 'lights': lights, 'alarms': alarms, 'time_zone': config['time_zone'],
                        'runtime': dict(runtime, error=self.error) if runtime.get('project') == layout['project'] else {'error': self.error}}
            if operation == 'stop':
                if saved:
                    saved['enabled'] = False
                    raw['revision'] += 1
                    e.write(raw)
                self.tick()
                return {'stopped': True, 'runtime': self.runtime()}
            if operation not in ('preview', 'apply'):
                raise ValueError('Operazione presenza non valida')
            selected = payload.get('lights')
            if not isinstance(selected, list) or not 1 <= len(selected) <= 20 or any(not isinstance(x, str) for x in selected) or len(set(selected)) != len(selected):
                raise ValueError('Scegli da 1 a 20 luci distinte')
            eligible = {x['entity']: x for x in lights}
            if any(x not in eligible or eligible[x]['state'] not in ('on', 'off') for x in selected):
                raise ValueError('Scegli luci disponibili del progetto')
            blocked = self.conflicts(layout, raw, states)
            if set(selected) & blocked:
                raise ValueError('Una luce scelta ha un programma attivo. Mettilo in pausa prima di abilitare la presenza simulata; la settimana rimarrà salvata.')
            start, end = payload.get('start'), payload.get('end')
            if any(not isinstance(v, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', v) for v in (start, end)) or start == end:
                raise ValueError('Imposta orari diversi per inizio e fine')
            values = {}
            for key, low, high in [('gap_min', 1, 120), ('gap_max', 1, 120), ('on_min', 1, 60), ('on_max', 1, 60)]:
                v = payload.get(key)
                if type(v) is not int or not low <= v <= high:
                    raise ValueError('Intervalli 1–120 minuti, accensioni 1–60 minuti')
                values[key] = v
            if values['gap_min'] > values['gap_max'] or values['on_min'] > values['on_max']:
                raise ValueError('Il minimo non può superare il massimo')
            mode, alarm = payload.get('mode'), payload.get('alarm', '')
            if mode not in ('manual', 'alarm') or mode == 'alarm' and alarm not in {a['entity'] for a in alarms}:
                raise ValueError('Scegli avvio manuale o un antifurto disponibile')
            clean = dict(lights=sorted(selected), start=start, end=end, mode=mode, alarm=alarm if mode == 'alarm' else '', **values)
            proof = digest({'config': clean, 'layout': layout, 'revision': raw['revision'], 'zone': config['time_zone']})
            if operation == 'preview':
                return {'preview_hash': proof, 'config': clean, 'names': [eligible[x]['name'] for x in selected], 'time_zone': config['time_zone']}
            if payload.get('preview_hash') != proof:
                raise ValueError('Anteprima cambiata: verifica nuovamente')
            if self.runtime().get('owned'):
                raise ValueError('Ferma prima la simulazione in corso e attendi il rilascio della luce')
            clean.update(enabled=True, layout_hash=digest(layout), arm=digest([proof, datetime.now(timezone.utc).isoformat()]))
            raw.setdefault('presence', {})[layout['project']] = clean
            raw['revision'] += 1
            e.write(raw)
            return {'saved': True}

    def release(self, ws, runtime, states, now):
        owned = runtime.get('owned')
        if not owned:
            return True
        state = next((s for s in states if s['entity_id'] == owned['entity']), None)
        if not state or state['state'] in ('unknown', 'unavailable'):
            runtime['message'] = 'Luce non disponibile: spegnimento in attesa del collegamento'
            self.write(runtime)
            return False
        if state['state'] == 'off':
            runtime.pop('owned', None)
        elif owned.get('signature') and light_signature(state) == owned['signature']:
            # Persist intent before the send; a retry only acts on the same state.
            ws.call('call_service', domain='light', service='turn_off', target={'entity_id': owned['entity']}, service_data={})
            owned['releasing'] = True
            runtime['message'] = 'Spegnimento richiesto; attendo conferma'
            self.write(runtime)
            return False
        else:
            runtime.pop('owned', None)
            runtime['message'] = 'Luce modificata manualmente o esito incerto: lasciata invariata'
        self.write(runtime)
        return True

    def tick(self, now=None):
        now = now or datetime.now(timezone.utc)
        e = self.e
        with LAYOUT_LOCK, e.lock:
            if e.reset_pending():
                return
            raw, original = e.read(), e.layout_provider()
            layout = e.combined(original, raw)
            saved = raw.get('presence', {}).get(layout.get('project'), {})
            runtime = self.runtime()
            if not saved.get('enabled') and not runtime.get('owned'):
                return
            with e.connection_factory() as ws:
                states = ws.call('get_states')
                inventory = {s['entity_id']: s for s in states}
                config = ws.call('get_config')
                alarm_state = inventory.get(saved.get('alarm'), {}).get('state')
                allowed_alarm = saved.get('mode') == 'manual' or alarm_state == ('on' if saved.get('alarm', '').startswith('input_boolean.nm_presence_sim_') else 'armed_away')
                active = bool(saved.get('enabled') and saved.get('layout_hash') == digest(layout) and allowed_alarm and in_window(now, config['time_zone'], saved['start'], saved['end']))
                blocked = self.conflicts(layout, raw, states) if active else set()
                if blocked & set(saved.get('lights', [])):
                    active = False
                    runtime['message'] = 'Sospesa: una luce ha una programmazione attiva'
                owned = runtime.get('owned')
                if owned and not owned.get('signature'):
                    state = inventory.get(owned['entity'], {})
                    try:
                        delay = (datetime.fromisoformat(state.get('last_changed', '')) - datetime.fromisoformat(owned['requested'])).total_seconds()
                    except ValueError:
                        delay = -1
                    if state.get('state') == 'on' and 0 <= delay <= 30:
                        owned['signature'] = light_signature(state)
                        self.write(runtime)
                    elif (now - datetime.fromisoformat(owned['requested'])).total_seconds() < 30 and active:
                        return
                if owned:
                    expired = now >= datetime.fromisoformat(owned['until'])
                    changed = owned.get('signature') and inventory.get(owned['entity']) and light_signature(inventory[owned['entity']]) != owned['signature']
                    if not active or expired or changed or owned.get('releasing') or self.recover:
                        if not self.release(ws, runtime, states, now):
                            return
                        runtime['next_at'] = (now + timedelta(minutes=self.random.randint(saved.get('gap_min', 5), saved.get('gap_max', 5)))).isoformat()
                        self.write(runtime)
                    else:
                        return
                if self.recover:
                    self.recover = False
                    runtime['next_at'] = (now + timedelta(minutes=saved.get('gap_min', 1))).isoformat()
                runtime['project'] = layout.get('project')
                if not active:
                    runtime['running'] = False
                    runtime['message'] = 'Ferma / in attesa di orario o antifurto' if not blocked else runtime['message']
                    if saved.get('enabled') and saved.get('layout_hash') != digest(layout):
                        runtime['message'] = 'Progetto modificato: verifica di nuovo la configurazione presenza'
                    self.write(runtime)
                    return
                runtime['running'] = True
                if runtime.get('arm') != saved['arm']:
                    runtime['arm'] = saved['arm']
                    runtime['next_at'] = now.isoformat()
                if now < datetime.fromisoformat(runtime.get('next_at', now.isoformat())):
                    self.write(runtime)
                    return
                eligible = [s for s in states if s['entity_id'] in saved['lights'] and s['state'] == 'off']
                runtime['next_at'] = (now + timedelta(minutes=self.random.randint(saved['gap_min'], saved['gap_max']))).isoformat()
                if not eligible:
                    runtime['message'] = 'Nessuna luce spenta disponibile: nessun comando'
                    self.write(runtime)
                    return
                choices = [s for s in eligible if s['entity_id'] != runtime.get('last_entity')] or eligible
                state = self.random.choice(choices)
                runtime['owned'] = {'entity': state['entity_id'], 'requested': now.isoformat(), 'until': (now + timedelta(minutes=self.random.randint(saved['on_min'], saved['on_max']))).isoformat()}
                runtime['last_entity'] = state['entity_id']
                runtime['message'] = 'Accensione simulata: ' + state['entity_id']
                self.write(runtime)
                ws.call('call_service', domain='light', service='turn_on', target={'entity_id': state['entity_id']}, service_data={})
                after = next((s for s in ws.call('get_states') if s['entity_id'] == state['entity_id']), None)
                if after and after['state'] == 'on':
                    runtime['owned']['signature'] = light_signature(after)
                    self.write(runtime)
