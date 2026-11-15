"""Append project cards to an existing storage dashboard after a reviewed preview."""
import copy
import json
import re
import time
from pathlib import Path
try:
    from .climate_cards import config, prepare
    from .control_engine import digest
except ImportError:
    from climate_cards import config, prepare
    from control_engine import digest

def integration(engine,payload):
    with engine.lock:
        layout,raw=engine.layout_provider(),engine.read();engine.guard(payload,layout,raw)
        layout=engine.combined(layout,raw)
        with engine.connection_factory() as ws:
            dashboards=ws.call('lovelace/dashboards/list')
            if payload.get('operation')=='list':
                return {'dashboards':[{'url_path':'lovelace','title':'Panoramica classica /lovelace (se presente)'}]+[{'url_path':d['url_path'],'title':d['title']} for d in dashboards if d.get('mode','storage')=='storage']}
            path=payload.get('url_path')
            if path!='lovelace' and not any(d['url_path']==path and d.get('mode','storage')=='storage' for d in dashboards):raise ValueError('Scegli una dashboard esistente modificabile')
            selected=payload.get('entities')
            if not isinstance(selected,list) or not 1<=len(selected)<=50 or len(set(selected))!=len(selected):raise ValueError('Seleziona da 1 a 50 dispositivi distinti')
            cards=[]
            for entity in selected:
                widgets=[w for w in layout['widgets'] if w.get('entity_id')==entity and w['type'] in ('climate','light','dimmer','cover','homeassistant')]
                if len(widgets)!=1 or not re.fullmatch(r'(climate|light|switch|cover)\.[a-z0-9_]+',entity):raise ValueError('Dispositivo non associato al progetto o duplicato')
                w=widgets[0];c=config(layout['project'],entity,w['name'])
                if w.get('command_mode')=='off_only':c['actions']=['off']
                elif w['type']=='light':c['actions']=['on','off']
                cards.append(c)
            args={} if path=='lovelace' else {'url_path':path}
            try:current=ws.call('lovelace/config',**args)
            except Exception as exc:raise ValueError('Dashboard automatica o non modificabile: seleziona una plancia HA personalizzabile. La nuova Panoramica automatica non ammette viste aggiuntive. Nessuna modifica applicata.') from exc
            if not isinstance(current,dict) or not isinstance(current.get('views'),list):raise ValueError('Dashboard senza configurazione modificabile')
            updated=copy.deepcopy(current);view_path='nm-dispositivi-'+layout['project'][:12]
            view=next((v for v in updated['views'] if v.get('path')==view_path),None)
            if view is None:
                view={'title':'NM · Dispositivi','path':view_path,'icon':'mdi:home-automation','cards':[]};updated['views'].append(view)
            if not isinstance(view.get('cards'),list):raise ValueError('La sezione NM è stata riorganizzata: scegli un’altra plancia per evitare di sovrascriverla')
            existing={c.get('entity') for c in view['cards'] if isinstance(c,dict)}
            additions=[c for c in cards if c['entity'] not in existing];view['cards'].extend(additions)
            fingerprint=digest({'current':current,'selected':selected,'project':layout['project']})
            summary={'url_path':path,'view_path':view_path,'added':[c['name'] for c in additions],'existing':len(cards)-len(additions),'fingerprint':fingerprint}
            if payload.get('operation')!='apply':return summary
            if payload.get('confirm') is not True or payload.get('expected_fingerprint')!=fingerprint:raise ValueError('La dashboard è cambiata: ripeti anteprima e conferma')
            if not additions:return {**summary,'unchanged':True}
            backup=Path(engine.root)/'nm_dashboard_card_backups';backup.mkdir(parents=True,exist_ok=True)
            with (backup/(re.sub('[^a-zA-Z0-9_-]','_',path)+'-'+str(time.time_ns())+'.json')).open('x',encoding='utf-8') as f:json.dump(current,f,ensure_ascii=False)
            prepare(updated,ws,root=engine.root)
            if digest(ws.call('lovelace/config',**args))!=digest(current):raise ValueError('Dashboard cambiata durante la preparazione: nessuna scrittura, ripeti anteprima')
            ws.call('lovelace/config/save',config=updated,**args)
            if ws.call('lovelace/config',**args)!=updated:raise ValueError('Verifica dashboard fallita: copia precedente conservata')
            return {**summary,'updated':True}
