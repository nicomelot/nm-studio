"""HA climate card provisioning and weekly plans executed by the NM scheduler.

Seven HA input_texts contain versioned days, an eighth is the atomic commit.
Incomplete/concurrent writes cannot activate a mixed week. No browser credentials.
"""
import json
import os
import re
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timezone

LOCK = threading.RLock()
CARD = 'custom:nm-climate-card'


def key(project, entity):
    return hashlib.sha256((project+':'+entity).encode()).hexdigest()[:20]


def config(project, entity, name):
    return {'type':CARD,'entity':entity,'project':project,'name':name,'grid_options':{'columns':12}}


def read(root='/data'):
    p=Path(root)/'nm_climate_cards.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def write(data, root):
    p=Path(root)/'nm_climate_cards.json';p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf-8');os.replace(tmp,p)


def install_resource(ws, root='/homeassistant'):
    name='nm-climate-card-5.34.1.js';url='/local/nm-control/'+name
    directory=Path(root)/'www'/'nm-control';directory.mkdir(parents=True,exist_ok=True)
    (directory/name).write_bytes(Path(__file__).with_name('nm-climate-card.js').read_bytes())
    resources=ws.call('lovelace/resources')
    old=next((r for r in resources if r.get('url','').startswith('/local/nm-control/nm-climate-card-')),None)
    if old:
        if old['url']!=url:ws.call('lovelace/resources/update',resource_id=old['id'],res_type='module',url=url)
    else:ws.call('lovelace/resources/create',res_type='module',url=url)


def prepare(config_, ws, root='/data', config_root='/homeassistant'):
    cards=[]
    def walk(v):
        if isinstance(v,dict):
            if v.get('type')==CARD:cards.append(v)
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(config_)
    if not cards:return
    with LOCK:
        data=read(root)
        for c in cards:
            project,entity=c.get('project',''),c.get('entity','')
            if not re.fullmatch('[a-f0-9]{64}',project) or not re.fullmatch(r'climate\.[a-z0-9_]+',entity):raise ValueError('Identità card clima non valida')
            ident=key(project,entity)
            row=data.setdefault(ident,{'project':project,'entity':entity,'days':[]})
            # Persist each helper so a failed installation can resume without duplicates.
            while len(row['days'])<7:
                helper=ws.call('input_text/create',name=f'nm_week_{ident}_{len(row["days"])}',max=255)
                row['days'].append('input_text.'+helper['id']);write(data,root)
            if not row.get('commit'):
                helper=ws.call('input_text/create',name=f'nm_week_{ident}_commit',max=255)
                row['commit']='input_text.'+helper['id'];write(data,root)
            if not row.get('status'):
                helper=ws.call('input_text/create',name=f'nm_week_{ident}_status',max=255)
                row['status']='input_text.'+helper['id'];write(data,root)
            c['schedule']={'days':row['days'],'commit':row['commit'],'status':row['status']}
            for name,value in row.get('options',{}).items():c.setdefault(name,value)
        install_resource(ws,config_root)


def records(root, layout, states, binding):
    inventory={s['entity_id']:s for s in states};result=[]
    for ident,row in read(root).items():
        if row['project']!=layout.get('project'):continue
        widgets=[w for w in layout['widgets'] if w.get('entity_id')==row['entity'] and w['type']=='climate']
        if len(widgets)!=1:continue
        w=widgets[0]
        record={'id':'haweek_'+ident,'kind':'schedule','name':'Settimana HA · '+w['name'],'room':w['room'],'enabled':False,'source':'ha_card','status_entity':row.get('status'),'actions':[{'device':binding(w),'action':'temperature','value':20}],'triggers':[],'warning':None,'activated_at':datetime.now(timezone.utc).isoformat()}
        try:
            commit=json.loads(inventory.get(row['commit'],{}).get('state',''))
            if not isinstance(commit,dict) or type(commit.get('enabled')) is not bool:raise ValueError('Settimana non ancora salvata')
            version=commit.get('v')
            if not isinstance(version,str) or not re.fullmatch('[a-f0-9]{32}',version):raise ValueError('Versione settimana non valida')
            for day,eid in enumerate(row['days']):
                value=json.loads(inventory.get(eid,{}).get('state',''))
                if value.get('v')!=version:raise ValueError('Salvataggio settimana incompleto: programma sospeso')
                slots=value.get('s')
                if not isinstance(slots,list) or len(slots)>8:raise ValueError('Massimo 8 fasce per giorno')
                seen=set()
                for slot in slots:
                    if not isinstance(slot,list) or len(slot)!=2:raise ValueError('Fascia non valida')
                    time,temp=slot
                    if not isinstance(time,str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',time) or time in seen:raise ValueError('Orario non valido o duplicato')
                    seen.add(time)
                    if type(temp) not in (int,float) or not -50<=temp<=100:raise ValueError('Temperatura non valida')
                    record['triggers'].append({'id':f'd{day}_{len(seen)}','kind':'time','time':time,'days':[day],'value':temp})
            if not record['triggers']:raise ValueError('Aggiungi almeno una fascia')
            # HA timestamp, not a client-supplied clock. Never replay older slots after activation.
            record['activated_at']=inventory[row['commit']]['last_changed']
            if datetime.fromisoformat(record['activated_at']).tzinfo is None:raise ValueError('Ora attivazione non valida')
            record['enabled']=commit['enabled']
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            record['warning']='Settimana non valida o non ancora salvata' if isinstance(exc,json.JSONDecodeError) else str(exc) or 'Settimana non valida';record['enabled']=False
        result.append(record)
    return result


def setup(engine, payload):
    try:
        from .dashboard_publisher import publish_generated
        from .control_engine import digest
    except ImportError:
        from dashboard_publisher import publish_generated
        from control_engine import digest
    with engine.lock:
        layout,raw=engine.layout_provider(),engine.read();engine.guard(payload,layout,raw)
        layout=engine.combined(layout,raw)
        widget=next((w for w in layout['widgets'] if w.get('entity_id')==payload.get('entity') and w['type']=='climate'),None)
        if not widget:raise ValueError('Scegli un termostato associato al progetto')
        entity=widget['entity_id'];project=layout['project'];ident=key(project,entity)
        c=config(project,entity,widget['name']);path='nm-studio-clima-'+ident
        with engine.connection_factory() as ws:
            dashboards=ws.call('lovelace/dashboards/list')
            if any(d['url_path']==path for d in dashboards):
                install_resource(ws)
                return {'url_path':path,'existing':True}
            if payload.get('simulated_options'):
                if not entity.startswith('climate.nm_lab_'+project[:12]+'_'):raise ValueError('Le opzioni simulate sono riservate a un termostato NM LAB del progetto')
                with LOCK:
                    data=read(engine.root);row=data.setdefault(ident,{'project':project,'entity':entity,'days':[]});opts=row.setdefault('options',{})
                    for name,domain,extra in [('filter_alarm','input_boolean',{}),('fan_auto','input_boolean',{}),('vane_position','input_number',{'min':0,'max':100,'step':1,'mode':'slider'})]:
                        if name not in opts:
                            helper=ws.call(domain+'/create',name='SIM '+name+' '+ident,**extra)
                            opts[name]=domain+'.'+helper['id'];write(data,engine.root)
                    c.update(opts)
            prepare(c,ws,root=engine.root)
        cards=[c]
        if payload.get('simulated_options'):
            cards.append({'type':'entities','title':'Collaudo · ingressi simulati','entities':[{'entity':c['filter_alarm'],'name':'SIM · Filtro da pulire'},{'entity':c['vane_position'],'name':'SIM · Palette %'},{'entity':c['fan_auto'],'name':'SIM · Ventola automatica'}]})
        generated={'dashboard':{'title':'Termostato · '+widget['name'],'views':[{'title':'Clima','path':'clima','cards':cards}]},'url_path':path,'summary':{'tiles':1},'warnings':[]}
        generated['fingerprint']=digest(generated['dashboard'])
        return publish_generated({'confirm':True,'title':('Termostato · '+widget['name'])[:60],'url_path':path,'expected_fingerprint':generated['fingerprint']},generated,engine.connection_factory)
