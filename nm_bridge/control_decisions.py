"""Explicit review of model suggestions; execution restricted to project lab entities."""
import copy
import secrets
import time

try:
    from .intelligence import summarize
except ImportError:
    from intelligence import summarize


def simulated(entity, project):
    return isinstance(entity, str) and entity.split('.', 1)[-1].startswith('nm_lab_' + project[:12] + '_')


class ControlDecisions:
    def __init__(self, engine):
        self.engine = engine
        self.previews = {}

    def review(self, payload, apply=False):
        try:
            from .control_engine import LAYOUT_LOCK, binding, clean_actions, digest, service_plan
        except ImportError:
            from control_engine import LAYOUT_LOCK, binding, clean_actions, digest, service_plan
        e = self.engine
        with LAYOUT_LOCK, e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
            with e.connection_factory() as ws:
                states = ws.call('get_states')
                decision = summarize(states)
                index = payload.get('proposal')
                if (not decision['valid'] or decision['decision_id'] != payload.get('decision_id') or
                        type(index) is not int or not 0 <= index < len(decision['proposals'])):
                    raise ValueError('Suggerimento scaduto o cambiato: aggiorna Decision Model')
                actions = clean_actions(payload.get('actions'), layout)
                entities = {w['entity_id'] for w in layout['widgets'] if any(a['device'] == binding(w) for a in actions)}
                if len(actions) != 1 or not all(simulated(entity, layout['project']) for entity in entities):
                    raise ValueError('Il collaudo Decision Model accetta un solo dispositivo simulato del progetto')
                calls = service_plan(layout, actions, ws)
            before = [{k: s.get(k) for k in ('entity_id', 'state', 'attributes')} for s in states if s['entity_id'] in entities]
            signature = digest({'decision': {k: decision[k] for k in ('decision_id','generated_at','expires_at','proposals')},
                                'layout': layout, 'actions': actions, 'before': before, 'revision': raw['revision']})
            now = time.monotonic()
            self.previews = {k:v for k,v in self.previews.items() if v['until'] > now}
            if apply:
                preview = self.previews.pop(payload.get('token', ''), None)
                if not preview or preview['signature'] != signature:
                    raise ValueError('Anteprima scaduta o dati cambiati: verifica di nuovo la modifica')
                key = 'decision:' + digest([layout['project'], decision['decision_id'], index])
                return e.execute(layout, {'name': 'Decision Model · ' + decision['proposals'][index]['action'][:60]}, actions, key)
            if len(self.previews) >= 100:
                raise ValueError('Troppe anteprime aperte: attendi due minuti')
            token = secrets.token_urlsafe(24)
            self.previews[token] = {'until': now + 120, 'signature': signature}
            return {'token': token, 'before': copy.deepcopy(before), 'calls': calls,
                    'proposal': decision['proposals'][index], 'simulation': True, 'expires_in': 120}

    def preview(self, payload):
        return self.review(payload)

    def apply(self, payload):
        return self.review(payload, apply=True)
