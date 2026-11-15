"""Widgets for existing HA entities; explicit, capability-checked commands."""
import hashlib
import json
import secrets
import time

DOMAINS = {'light', 'switch', 'input_boolean', 'button', 'input_button', 'media_player', 'sensor', 'binary_sensor', 'event'}
ATTRIBUTES = ('brightness', 'supported_color_modes', 'supported_features', 'volume_level',
              'is_volume_muted', 'source', 'source_list', 'media_title', 'unit_of_measurement',
              'device_class', 'event_type')


def actions(state):
    domain = state.get('entity_id', '').split('.')[0]
    attrs = state.get('attributes') or {}
    if domain in ('switch', 'input_boolean'):
        return ['on', 'off']
    if domain == 'light':
        return ['on', 'off'] + (['brightness'] if set(attrs.get('supported_color_modes') or []) - {'onoff', 'unknown'} else [])
    if domain in ('button', 'input_button'):
        return ['press']
    if domain == 'media_player':
        flags = attrs.get('supported_features', 0)
        if type(flags) is not int:
            return []
        return [action for action, bit in [('on',128),('off',256),('play',16384),('pause',1),('volume',4),('mute',8),('source',2048)] if flags & bit]
    return []


def plan(widget, action, value, states):
    entity = widget['entity_id']
    state = next((s for s in states if s['entity_id'] == entity), None)
    if not state or state['state'] == 'unavailable' or (state['state'] == 'unknown' and action != 'press'):
        raise ValueError('Dispositivo non disponibile')
    if action not in actions(state):
        raise ValueError('Comando non supportato dal dispositivo')
    domain = entity.split('.')[0]
    service = {'on':'turn_on','off':'turn_off','brightness':'turn_on','press':'press',
               'play':'media_play','pause':'media_pause','volume':'volume_set','mute':'volume_mute','source':'select_source'}[action]
    data = {}
    if action in ('brightness','volume'):
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError('Inserisci una percentuale intera da 0 a 100')
        data = {'brightness_pct':value} if action == 'brightness' else {'volume_level':value/100}
    elif action == 'mute':
        if type(value) is not bool:
            raise ValueError('Stato silenzioso non valido')
        data = {'is_volume_muted':value}
    elif action == 'source':
        if not isinstance(value, str) or value not in (state.get('attributes', {}).get('source_list') or []):
            raise ValueError('Sorgente non disponibile')
        data = {'source':value}
    return {'domain':domain, 'service':service, 'target':{'entity_id':entity}, 'service_data':data}, state


class HomeAssistantWidgets:
    def __init__(self, engine, binding):
        self.engine, self.binding, self.previews = engine, binding, {}

    def handle(self, payload, apply=False):
        try:
            from .widget_layout import LAYOUT_LOCK
        except ImportError:
            from widget_layout import LAYOUT_LOCK
        e = self.engine
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
            widgets = e.features.widgets(layout['project'], raw)
            widget = next((w for w in widgets if w['type']=='homeassistant' and self.binding(w)==payload.get('device')), None)
            if not widget:
                raise ValueError('Widget Home Assistant non presente nel progetto')
            action, value = payload.get('action'), payload.get('value')
            with e.connection_factory() as ws:
                call, before = plan(widget, action, value, ws.call('get_states'))
            signature = hashlib.sha256(json.dumps({'widget':widget,'call':call,'state':before['state'],
                'attributes':{k:before.get('attributes',{}).get(k) for k in ATTRIBUTES},
                'project':layout['project'],'revision':raw['revision']},sort_keys=True).encode()).hexdigest()
            now = time.monotonic()
            self.previews = {k:v for k,v in self.previews.items() if v['until']>now}
            if apply:
                token = payload.get('token','')
                preview = self.previews.pop(token, None)
                if not preview or preview['signature'] != signature:
                    raise ValueError('Anteprima scaduta o dispositivo cambiato: ripeti la verifica')
                def planner(_layout, _actions, ws):
                    return [plan(widget, action, value, ws.call('get_states'))[0]]
                return e.execute(layout, {'name':'Home Assistant · '+widget['name']}, [],
                                 'ha-widget:'+token, planner=planner)
            if len(self.previews)>=100:
                raise ValueError('Troppe anteprime aperte: attendi due minuti')
            token = secrets.token_urlsafe(24)
            self.previews[token] = {'until':now+120,'signature':signature}
            return {'token':token,'entity_id':widget['entity_id'],'state':before['state'],'call':call}

    def preview(self, payload):
        return self.handle(payload)

    def apply(self, payload):
        return self.handle(payload, True)
