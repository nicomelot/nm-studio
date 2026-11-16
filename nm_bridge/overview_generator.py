"""Reviewed overview generation. Manually edited or removed HA views always win."""
import copy
import json
import re
import time
from pathlib import Path
try:
    from .control_engine import digest, catalog
    from .climate_cards import config, prepare, read as read_cards, key
    from .diagram_publisher import generate as diagram, install_resource
    from .dashboard_publisher import _save_baseline, _read_baseline
except ImportError:
    from control_engine import digest, catalog
    from climate_cards import config, prepare, read as read_cards, key
    from diagram_publisher import generate as diagram, install_resource
    from dashboard_publisher import _save_baseline, _read_baseline

DOMAINS = {'light','switch','cover','climate','sensor','binary_sensor','fan','media_player','button','input_button'}

def eligible(w, present):
    entity=w.get('entity_id','')
    return entity in present and entity.split('.')[0] in DOMAINS and w['type']!='momentary'

def build(layout, states, plans, payload, root):
    present={s['entity_id'] for s in states}
    selected=payload.get('entities',[]); chosen=payload.get('plans',[])
    if not isinstance(selected,list) or not isinstance(chosen,list) or len(selected)>300 or len(chosen)>30 or not all(isinstance(x,str) for x in selected+chosen) or len(set(selected))!=len(selected) or len(set(chosen))!=len(chosen):
        raise ValueError('Selezione dispositivi o schemi non valida')
    widgets={w['entity_id']:w for w in layout['widgets'] if eligible(w,present)}
    if any(e not in widgets for e in selected):raise ValueError('Un dispositivo non esiste più in HA: riapri il generatore')
    by_plan={p['id']:p for p in plans}
    if any(p not in by_plan for p in chosen):raise ValueError('Uno schema non esiste più: riapri il generatore')
    if not selected and not chosen:raise ValueError('Seleziona almeno un dispositivo o uno schema')
    project=layout['project']; prefix='nm-'+project[:12]
    grouped={}; metadata=read_cards(root)
    for entity in selected:
        w=widgets[entity]; domain=entity.split('.')[0]
        if domain in {'light','switch','cover','climate'}:
            c=config(project,entity,w['name']);c['grid_options']={'columns':12,'rows':'auto'}
            if w.get('command_mode')=='off_only':c['actions']=['off']
            elif w['type']=='light':c['actions']=['on','off']
            # Existing helpers/options are reused; no new week and no activation.
            row=metadata.get(key(project,entity),{})
            if row.get('days'):c['schedule']={k:row[k] for k in ('days','commit','status') if k in row}
            for option in ('filter_alarm','fan_auto','vane_position'):
                if option in row.get('options',{}):c[option]=row['options'][option] if row['options'][option] in present else ''
        else:c={'type':'tile','entity':entity,'name':w['name']}
        grouped.setdefault(w.get('room') or 'Da assegnare',[]).append(c)
    views=[];sections=[]
    for room,cards in grouped.items():
        sections.append({'type':'grid','cards':[{'type':'heading','heading':room.split(' / ')[-1],'icon':'mdi:home-outline'},*cards]})
    devices=catalog(layout,states)
    warnings=[]
    for ident in chosen:
        p=by_plan[ident]
        if p['kind']=='floorplan' and not p.get('background'):raise ValueError('Salva uno sfondo per '+p['name'])
        if not p.get('points') and not p.get('pipes') and not p.get('background'):raise ValueError('Schema vuoto: '+p['name'])
        v=diagram(p,devices,payload['url_path'])['views'][0]
        v['path']=prefix+'-schema-'+digest(ident)[:10]
        v['icon']='mdi:floor-plan' if p['kind']=='floorplan' else 'mdi:heat-pump'
        for point in v['cards'][0]['points']:
            if point.get('entity') not in present:
                point['entity']=''
                warnings.append(p['name']+' · '+point['label']+': solo documentazione, entità assente')
        views.append(v)
    home={'title':'Casa','path':prefix+'-casa','icon':'mdi:home','type':'sections','max_columns':3,'sections':sections}
    # Only actual generated views get navigation buttons. No static placeholders.
    if views:
        home['sections'].append({'type':'grid','cards':[{'type':'heading','heading':'Esplora','icon':'mdi:floor-plan'}]+[{'type':'button','name':v['title'],'icon':v['icon'],'tap_action':{'action':'navigate','navigation_path':'/'+payload['url_path']+'/'+v['path']}} for v in views]})
    if payload.get('standard_cards',True):
        sensors=[e for e in selected if e.startswith('sensor.') and next((s.get('attributes',{}).get('device_class') for s in states if s['entity_id']==e),None)=='temperature']
        if sensors:home['sections'].append({'type':'grid','cards':[{'type':'history-graph','title':'Temperature','hours_to_show':12,'entities':sensors[:8]}]})
    return {'title':payload['title'],'views':[home,*views]}, warnings

def merge_views(base,current,new):
    """Conservative view-level merge: edited/reordered content is never rewritten."""
    old={v.get('path'):v for v in base.get('views',[])}
    fresh={v.get('path'):v for v in new['views']}
    result=copy.deepcopy(current);output=[];preserved=[];removed=[]
    seen=set()
    for view in current.get('views',[]):
        ident=view.get('path');seen.add(ident)
        if ident in old and view==old[ident]:
            if ident in fresh:output.append(copy.deepcopy(fresh[ident]))
            else:removed.append(view.get('title',ident))
        else:
            output.append(copy.deepcopy(view))
            if ident in fresh:preserved.append(view.get('title',ident))
    for ident,view in fresh.items():
        if ident not in seen and ident not in old:output.append(copy.deepcopy(view))
        elif ident not in seen:preserved.append(view.get('title',ident)+' (rimossa in HA)')
    # A generated home must not link to a view the user removed in HA.
    existing={v.get('path') for v in output}
    for view in output:
        if view.get('path') in fresh and view==fresh[view.get('path')]:
            for section in view.get('sections',[]):
                section['cards']=[c for c in section.get('cards',[]) if not c.get('tap_action',{}).get('navigation_path') or c['tap_action']['navigation_path'].rsplit('/',1)[-1] in existing]
            view['sections']=[s for s in view.get('sections',[]) if len(s.get('cards',[]))!=1 or s['cards'][0].get('type')!='heading']
    result['views']=output
    return result,preserved,removed

def integration(engine,payload):
    with engine.lock:
        layout,raw=engine.layout_provider(),engine.read();engine.guard(payload,layout,raw)
        layout=engine.combined(layout,raw)
        archive=engine.features.diagrams(payload)
        with engine.connection_factory() as ws:
            states=ws.call('get_states');present={s['entity_id'] for s in states}
            dashboards=ws.call('lovelace/dashboards/list')
            if payload.get('operation')=='list':
                return {'devices':[{'entity':w['entity_id'],'name':w['name'],'room':w['room'],'visible':w.get('visible',True),'available':next(s['state'] for s in states if s['entity_id']==w['entity_id']) not in ('unknown','unavailable')} for w in layout['widgets'] if eligible(w,present)],'excluded':len([w for w in layout['widgets'] if not eligible(w,present)]),'plans':[{'id':p['id'],'name':p['name'],'kind':p['kind'],'ready':bool(p.get('background') or p['kind']=='schematic' and (p.get('points') or p.get('pipes')))} for p in archive['plans']], 'dashboards':[{'url_path':d['url_path'],'title':d['title']} for d in dashboards if d.get('mode','storage')=='storage'], 'suggested_path':'nm-studio-casa-'+layout['project'][:12]}
            path=payload.get('url_path');title=payload.get('title')
            if not isinstance(path,str) or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)+',path) or len(path)>64:raise ValueError('Percorso: lettere minuscole, numeri e almeno un trattino, massimo 64 caratteri')
            if not isinstance(title,str) or not 3<=len(title.strip())<=60:raise ValueError('Nome Panoramica: da 3 a 60 caratteri')
            payload={**payload,'title':title.strip()}
            exists=any(d['url_path']==path for d in dashboards)
            if exists and not any(d['url_path']==path and d.get('mode','storage')=='storage' for d in dashboards):raise ValueError('Dashboard non modificabile')
            current=ws.call('lovelace/config',url_path=path) if exists else None
            if exists and (not isinstance(current,dict) or not isinstance(current.get('views'),list)):raise ValueError('Dashboard automatica non modificabile')
            base_dir=Path(engine.root)/'nm_overview_backups'
            base=_read_baseline(path,base_dir)
            generated,warnings=build(layout,states,archive['plans'],payload,engine.root)
            updated,preserved,removed=merge_views(base,current,generated) if exists else (copy.deepcopy(generated),[],[])
            fp=digest({'current':current,'base':base,'new':generated,'project':layout['project']})
            summary={'url_path':path,'exists':exists,'fingerprint':fp,'views':[{'title':v.get('title','Vista'),'path':v.get('path','')} for v in updated['views']],'devices':len(payload.get('entities',[])),'preserved':preserved,'removed':removed,'warnings':warnings,'unchanged':current==updated,'view_path':updated['views'][0].get('path','0') if updated['views'] else '0'}
            if payload.get('operation')!='apply':return summary
            if payload.get('expected_fingerprint')!=fp:raise ValueError('Anteprima cambiata: ripeti il confronto prima di applicare')
            if not updated['views']:raise ValueError('Nessuna vista: crea una nuova Panoramica')
            if current==updated:return summary
            base_dir.mkdir(parents=True,exist_ok=True)
            if current is not None:
                with (base_dir/(path+'-'+str(time.time_ns())+'.json')).open('x',encoding='utf-8') as f:json.dump(current,f,ensure_ascii=False)
            # Provision only changed/new views: prepare mutates schedule bindings.
            # A retained HA view must remain byte-for-byte unchanged, including
            # any user-selected helper entities and optional controls.
            retained=(current or {}).get('views',[])
            prepare({'views':[v for v in updated['views'] if v not in retained]},ws,root=engine.root)
            if any(c.get('type')=='custom:nm-floorplan-card' for v in updated['views'] for c in v.get('cards',[])):install_resource(ws)
            if exists:
                if ws.call('lovelace/config',url_path=path)!=current:raise ValueError('Dashboard modificata durante la preparazione: ripeti anteprima')
            else:
                if any(d['url_path']==path for d in ws.call('lovelace/dashboards/list')):raise ValueError('Percorso creato altrove: ripeti anteprima')
                ws.call('lovelace/dashboards/create',url_path=path,title=title.strip(),icon='mdi:home',show_in_sidebar=True,require_admin=False)
            try:
                ws.call('lovelace/config/save',url_path=path,config=updated)
                if ws.call('lovelace/config',url_path=path)!=updated:raise ValueError('Contenuto salvato diverso dall’anteprima')
            except Exception as exc:raise ValueError('Pubblicazione non verificata per '+path+'. Riapri il generatore; eventuale pagina vuota e backup sono conservati. '+str(exc)[:120]) from exc
            # Baseline must include provisioned helpers but not manual HA edits.
            helpers=read_cards(engine.root)
            def enrich(value):
                if isinstance(value,dict):
                    if value.get('type') in ('custom:nm-device-card','custom:nm-climate-card'):
                        row=helpers.get(key(value['project'],value['entity']),{})
                        if row.get('days'):value['schedule']={k:row[k] for k in ('days','commit','status') if k in row}
                    for child in value.values():enrich(child)
                elif isinstance(value,list):
                    for child in value:enrich(child)
            enrich(generated);_save_baseline(path,generated,base_dir)
            return {**summary,'updated':True}
