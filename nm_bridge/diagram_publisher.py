"""Create-only native HA page from one saved NM diagram, with technical subviews."""
import base64
import html
import hashlib
import json
import os
import time
from pathlib import Path
try:
    from .dashboard_publisher import HAWebSocket, PublishError, URL_PATH, _listed_paths
    from .floorplan_lovelace import ICON
except ImportError:
    from dashboard_publisher import HAWebSocket, PublishError, URL_PATH, _listed_paths
    from floorplan_lovelace import ICON

FIELDS={'rack':'Rack','patch_panel':'Patch panel','patch_port':'Porta patch panel','switch':'Switch','switch_port':'Porta switch','dali_line':'Linea DALI','dali_address':'Indirizzo ECG','dali_groups':'Gruppi DALI'}
ICONS={**ICON,'data':'mdi:ethernet','dali':'mdi:chip','knx':'mdi:chip','light':'mdi:lightbulb','temperature':'mdi:thermometer','button':'mdi:gesture-tap-button','pump':'mdi:pump','valve':'mdi:valve','boiler':'mdi:water-boiler','tank':'mdi:storage-tank','fan':'mdi:fan','motion':'mdi:motion-sensor','contact':'mdi:door-closed'}
def safe(value):
    return html.escape(str(value)).replace('{','&#123;').replace('}','&#125;')

def generate(plan, devices, url_path):
    if plan['kind'] not in ('floorplan','schematic'):raise PublishError('Tipo schema non valido')
    if plan['kind']=='floorplan' and not plan.get('background'):raise PublishError('Carica e salva uno sfondo prima di pubblicare')
    background=plan.get('background') or ('data:image/svg+xml;base64,'+base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="1200" height="800" fill="#12251e"/></svg>').decode())
    by_id={d['id']:d for d in devices}
    points=[]
    for p in plan['points']:
        d=by_id.get(p.get('device'),{})
        points.append({'label':p['label'],'x':p['x'],'y':p['y'],'icon':ICONS.get(p['symbol'],'mdi:map-marker'),'entity':d.get('entity_id',''),'notes':p.get('notes',''),'symbol':p['symbol'],'temp_low':p.get('temp_low',18),'temp_high':p.get('temp_high',28),'network':p.get('network',{}),'technical':p.get('technical',{}),'rows':[[n,p['technical'][k]] for k,n in FIELDS.items() if p.get('technical',{}).get(k)]})
    return {'title':plan['name'],'views':[{'title':plan['name'],'path':'mappa','type':'panel','cards':[{'type':'custom:nm-floorplan-card','title':plan['name'],'image':background,'points':points,'pipes':plan.get('pipes',[]),'kind':plan['kind']}]}]}

def digest(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()

def install_resource(client, config_root='/homeassistant'):
    name='nm-floorplan-card-5.34.0.js';url='/local/nm-control/'+name
    directory=Path(config_root)/'www'/'nm-control';directory.mkdir(parents=True,exist_ok=True)
    content=Path(__file__).with_name('nm-floorplan-card.js').read_bytes()
    target=directory/name;temp=directory/(name+'.tmp');temp.write_bytes(content);os.replace(temp,target)
    resources=client.call('lovelace/resources')
    if not isinstance(resources,list):raise PublishError('Elenco risorse HA non disponibile')
    existing=next((r for r in resources if str(r.get('url','')).startswith('/local/nm-control/nm-floorplan-card-')),None)
    if existing:
        if existing.get('url')!=url:client.call('lovelace/resources/update',resource_id=existing['id'],res_type='module',url=url)
    else:client.call('lovelace/resources/create',res_type='module',url=url)

def publish(payload, plan, devices, client_factory=HAWebSocket, config_root="/homeassistant", backup_root="/data/nm_diagram_backups"):
    if payload.get('confirm') is not True:raise PublishError('Conferma esplicita richiesta')
    title,path=payload.get('title'),payload.get('url_path')
    if not isinstance(title,str) or not 3<=len(title.strip())<=60:raise PublishError('Nome pagina: da 3 a 60 caratteri')
    if not isinstance(path,str) or not URL_PATH.fullmatch(path):raise PublishError('Percorso: nm-studio- seguito da lettere minuscole, numeri o trattini')
    config=generate(plan,devices,path);config['title']=title.strip()
    with client_factory() as client:
        exists=path in _listed_paths(client.call('lovelace/dashboards/list'))
        previous=client.call('lovelace/config',url_path=path) if exists else None
        if exists and payload.get('update_existing') is not True:raise PublishError('Pagina già esistente: seleziona Aggiorna pagina esistente')
        if payload.get('preview') is True:
            return {'exists':exists,'existing_fingerprint':digest(previous),'url_path':path}
        if exists:
            if payload.get('existing_fingerprint')!=digest(previous):raise PublishError('Pagina modificata: ripeti il confronto prima di aggiornare')
            backup=Path(backup_root);backup.mkdir(parents=True,exist_ok=True)
            with (backup/(path+'-'+str(time.time_ns())+'.json')).open('x',encoding='utf-8') as f:
                json.dump(previous,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        install_resource(client,config_root)
        if not exists:client.call('lovelace/dashboards/create',url_path=path,title=title.strip(),icon='mdi:floor-plan',show_in_sidebar=True,require_admin=False)
        try:
            client.call('lovelace/config/save',url_path=path,config=config)
            stored=client.call('lovelace/config',url_path=path)
            if not isinstance(stored,dict) or stored.get('views')!=config['views']:raise PublishError('Verifica contenuto non riuscita')
        except Exception as exc:raise PublishError(f'Pagina {path} creata ma contenuto non verificato: {str(exc)[:100]}') from exc
    return {'created':not exists,'updated':exists,'url_path':path}
