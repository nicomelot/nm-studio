"""Reviewed button-to-scene links using HA native trigger subscriptions.

No polling of last button values, no replay after reconnect. Each rule owns a
subscription; commands still pass the project's service allowlist and journal.
"""
import copy
import hashlib
import json
import threading
import time
import uuid

try:
    from .widget_layout import LAYOUT_LOCK
except ImportError:
    from widget_layout import LAYOUT_LOCK


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ControlButtons:
    def __init__(self, engine):
        self.e = engine
        self.worker = None
        self.health = {'connected': False, 'error': None, 'listening': 0}

    def rules(self, raw, project):
        return raw.get('button_links', {}).get(project, [])

    def sources(self, payload):
        e = self.e
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
        with e.connection_factory() as ws:
            states = ws.call('get_states')
            devices = ws.call('config/device_registry/list')
        return {'devices': [{'id': d['id'], 'name': d.get('name_by_user') or d.get('name') or d['id'],
                             'manufacturer': d.get('manufacturer') or ''} for d in devices],
                'entities': [{'id': s['entity_id'], 'name': s.get('attributes', {}).get('friendly_name', s['entity_id'])}
                             for s in states if s['entity_id'].split('.')[0] in ('event', 'input_button')]}

    def options(self, ws, source):
        if not isinstance(source, str):
            raise ValueError('Scegli un pulsante')
        result = []
        if source.startswith('device:'):
            device_id = source[7:]
            devices = ws.call('config/device_registry/list')
            if not any(d['id'] == device_id for d in devices):
                raise ValueError('Dispositivo non presente in Home Assistant')
            triggers = ws.call('device_automation/trigger/list', device_id=device_id) or []
            for t in triggers:
                gesture = str(t.get('type',''))+' '+str(t.get('subtype',''))
                if not any(word in gesture.lower() for word in ('press','click','hold','release','single','double','triple','long')):
                    continue
                trigger = {k:v for k,v in t.items() if k != 'metadata'}
                result.append({'label': ' · '.join(str(t[k]) for k in ('type','subtype') if t.get(k)), 'trigger': trigger})
        elif source.startswith('entity:'):
            entity = source[7:]
            state = next((s for s in ws.call('get_states') if s['entity_id'] == entity), None)
            if not state or entity.split('.')[0] not in ('event', 'input_button'):
                raise ValueError('Scegli una entità evento o pulsante simulato')
            types = state.get('attributes', {}).get('event_types', []) if entity.startswith('event.') else ['press']
            for event_type in types:
                if not isinstance(event_type, str):
                    continue
                trigger = {'platform':'state', 'entity_id':entity, 'not_to':['unknown','unavailable'], 'not_from':['unavailable'] if entity.startswith('input_button.') else ['unknown','unavailable']}
                # Event entities carry a new timestamp for repeated identical presses.
                # Filtering event_type happens on the received to_state, not on its change.
                result.append({'label':event_type, 'trigger':trigger, 'event_type':event_type if entity.startswith('event.') else None})
        else:
            raise ValueError('Origine pulsante non valida')
        for item in result:
            item['id'] = digest(item)
        return result

    def triggers(self, payload):
        e = self.e
        with LAYOUT_LOCK, e.lock:
            e.guard(payload, e.layout_provider(), e.read())
        with e.connection_factory() as ws:
            return {'options': self.options(ws, payload.get('source'))}

    def review(self, payload, save=False):
        e = self.e
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
            scene = next((r for r in e.records(raw, layout['project']) if r['id']==payload.get('scene') and r['kind']=='scene'), None)
            if not scene:
                raise ValueError('Scegli uno scenario salvato')
            if any(a['action']=='press' for a in scene['actions']):
                raise ValueError('Uno scenario collegato a un pulsante non può premere altri pulsanti: evita richiami circolari')
            source = payload.get('source')
            with e.connection_factory() as ws:
                option = next((t for t in self.options(ws, source) if t['id']==payload.get('option')), None)
                if not option:
                    raise ValueError('Pressione non più disponibile: aggiorna il pulsante')
                try:
                    from .control_engine import service_plan
                except ImportError:
                    from control_engine import service_plan
                calls = service_plan(e.combined(layout, raw), scene['actions'], ws)
                # Validate by briefly subscribing, without processing any events or commands.
                ws.call('subscribe_trigger', trigger=option['trigger'])
                subscription = ws.sequence
                ws.call('unsubscribe_events', subscription=subscription)
            name = payload.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                raise ValueError('Inserisci un nome per il collegamento')
            proof = digest({'source':source,'option':option,'scene':scene,'layout':e.combined(layout,raw),'revision':raw['revision'],'name':name.strip(),'id':payload.get('id')})
            if not save:
                return {'preview_hash':proof,'label':option['label'],'scene':scene['name'],'actions':scene['actions'],'calls':calls}
            if payload.get('preview_hash') != proof:
                raise ValueError('Anteprima cambiata: verifica nuovamente')
            rules = raw.setdefault('button_links', {}).setdefault(layout['project'], [])
            old = next((r for r in rules if r['id']==payload.get('id')), None)
            if payload.get('id') and old is None:
                raise ValueError('Collegamento non trovato')
            if not old and len(rules) >= 100:
                raise ValueError('Limite di 100 collegamenti')
            if any(r is not old and r['source']==source and r['option']['id']==option['id'] and r.get('enabled') for r in rules):
                raise ValueError('Pressione già collegata: metti in pausa il collegamento esistente')
            ident = old['id'] if old else uuid.uuid4().hex
            if old:
                rules.remove(old)
            rules.append({'id':ident,'name':name.strip(),'source':source,'option':option,'scene':scene['id'],
                          'arm_id':uuid.uuid4().hex, 'scene_hash':digest(scene),'layout_hash':digest(e.combined(layout,raw)), 'enabled':True})
            raw['revision'] += 1
            e.write(raw)
            return {'saved':True,'id':ident}

    def pause(self, payload):
        e = self.e
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
            rule = next((r for r in self.rules(raw,layout['project']) if r['id']==payload.get('id')), None)
            if not rule:
                raise ValueError('Collegamento non trovato')
            rule['enabled'] = False
            raw['revision'] += 1
            e.write(raw)
            return {'paused':True}

    def active(self, layout, raw):
        scenes = {r['id']:r for r in self.e.records(raw,layout.get('project','')) if r['kind']=='scene'}
        return [r for r in self.rules(raw,layout.get('project','')) if r.get('enabled') and
                r['scene'] in scenes and r['scene_hash']==digest(scenes[r['scene']]) and
                r['layout_hash']==digest(self.e.combined(layout,raw))]

    def dispatch(self, project, rule, event):
        e = self.e
        # Ignore setup/restored states and unrelated attribute updates.
        variables = event.get('variables', {})
        trigger = variables.get('trigger', {})
        if rule['source'].startswith('entity:'):
            old, new = trigger.get('from_state'), trigger.get('to_state')
            if not old or not new or old.get('state') in (('unavailable',) if rule['source'].startswith('entity:input_button.') else ('unknown','unavailable')) or new.get('state') in ('unknown','unavailable') or old.get('state') == new.get('state'):
                return
            if rule['option'].get('event_type') and new.get('attributes',{}).get('event_type') != rule['option']['event_type']:
                return
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            if layout.get('project') != project or rule not in self.active(layout,raw):
                return
            scene = next(r for r in e.records(raw,project) if r['id']==rule['scene'])
            # Same received event cannot execute twice, including process restart.
            key = 'button:'+project+':'+rule['id']+':'+digest(event)
            return e.execute(e.combined(layout,raw), {**scene,'name':'Pulsante · '+rule['name']}, scene['actions'], key)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        def loop():
            while not self.e.stop_event.is_set():
                try:
                    with LAYOUT_LOCK, self.e.lock:
                        layout, raw = self.e.layout_provider(), self.e.read()
                        active = copy.deepcopy(self.active(layout,raw))
                        generation = (layout.get('project'), digest(layout), raw['revision'])
                    if not active:
                        self.health.update(connected=False, error=None, listening=0)
                        self.e.stop_event.wait(1)
                        continue
                    with self.e.connection_factory() as ws:
                        subscriptions = {}
                        for rule in active:
                            ws.call('subscribe_trigger', trigger=rule['option']['trigger'])
                            subscriptions[ws.sequence] = rule
                        ws.connection.settimeout(1)
                        ping_at = time.monotonic()
                        pending_ping = None
                        self.health.update(connected=True,error=None,listening=len(subscriptions))
                        while not self.e.stop_event.is_set():
                            with LAYOUT_LOCK, self.e.lock:
                                current, data = self.e.layout_provider(), self.e.read()
                                if generation != (current.get('project'),digest(current),data['revision']):
                                    break
                            if time.monotonic()-ping_at > 30:
                                if pending_ping is not None:
                                    raise TimeoutError('Home Assistant non risponde: riconnessione pulsanti')
                                ws.sequence += 1
                                pending_ping = ws.sequence
                                ws.connection.send(json.dumps({'id':pending_ping,'type':'ping'}))
                                ping_at = time.monotonic()
                            try:
                                message = ws._receive()
                            except TimeoutError:
                                continue
                            except Exception as exc:
                                if type(exc).__name__=='WebSocketTimeoutException':
                                    continue
                                raise
                            if message.get('type')=='pong' and message.get('id')==pending_ping:
                                pending_ping = None
                            if message.get('type')=='event' and message.get('id') in subscriptions:
                                self.dispatch(generation[0],subscriptions[message['id']],message.get('event',{}))
                except Exception as exc:
                    self.health.update(connected=False,error=str(exc)[:180],listening=0)
                    self.e.stop_event.wait(5)
                finally:
                    self.health['connected'] = False
        self.worker = threading.Thread(target=loop,name='nm-buttons',daemon=True)
        self.worker.start()
