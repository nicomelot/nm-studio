"""Create-only native HA page from one saved NM diagram, with technical subviews."""
import html
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
    if plan['kind']!='floorplan' or not plan.get('background'):raise PublishError('Carica e salva uno sfondo per la planimetria prima di pubblicare')
    if plan.get('pipes'):raise PublishError('La pubblicazione nativa non include le tubazioni: usa una planimetria senza tubi')
    by_id={d['id']:d for d in devices};elements=[];views=[]
    for i,p in enumerate(plan['points']):
        target=f'/{url_path}/punto-{i}'
        rows=[(label,p.get('technical',{}).get(key)) for key,label in FIELDS.items() if p.get('technical',{}).get(key)]
        tooltip='\n'.join([p['label']]+[f'{k}: {v}' for k,v in rows])
        element={'type':'icon','icon':ICONS.get(p['symbol'],'mdi:map-marker'),'title':tooltip,'style':{'left':f"{p['x']}%",'top':f"{p['y']}%",'background':'#152721e8','border-radius':'50%','padding':'8px','color':'#e4eee9'},'tap_action':{'action':'navigate','navigation_path':target},'hold_action':{'action':'none'},'double_tap_action':{'action':'none'}}
        d=by_id.get(p.get('device'));entity=d.get('entity_id') if d else None
        if entity:element.update(type='state-icon',entity=entity)
        elements.append(element)
        content='<h2>'+safe(p['label'])+'</h2>'+''.join(f'<p><b>{safe(k)}</b>: {safe(v)}</p>' for k,v in rows)
        if p.get('notes'):content+='<p>'+safe(p['notes']).replace('\n','<br>')+'</p>'
        cards=[{'type':'markdown','content':content}]
        if entity:cards.append({'type':'tile','entity':entity,'name':p['label'],'tap_action':{'action':'more-info'},'icon_tap_action':{'action':'more-info'}})
        else:cards.append({'type':'markdown','content':'Punto di documentazione. Nessun dispositivo collegato.'})
        views.append({'title':p['label'],'path':f'punto-{i}','subview':True,'back_path':f'/{url_path}/mappa','cards':cards})
    return {'title':plan['name'],'views':[{'title':plan['name'],'path':'mappa','type':'panel','cards':[{'type':'picture-elements','image':plan['background'],'elements':elements}]}]+views}

def publish(payload, plan, devices, client_factory=HAWebSocket):
    if payload.get('confirm') is not True:raise PublishError('Conferma esplicita richiesta')
    title,path=payload.get('title'),payload.get('url_path')
    if not isinstance(title,str) or not 3<=len(title.strip())<=60:raise PublishError('Nome pagina: da 3 a 60 caratteri')
    if not isinstance(path,str) or not URL_PATH.fullmatch(path):raise PublishError('Percorso: nm-studio- seguito da lettere minuscole, numeri o trattini')
    config=generate(plan,devices,path);config['title']=title.strip()
    with client_factory() as client:
        if path in _listed_paths(client.call('lovelace/dashboards/list')):raise PublishError('Pagina già esistente: scegli un nuovo percorso')
        client.call('lovelace/dashboards/create',url_path=path,title=title.strip(),icon='mdi:floor-plan',show_in_sidebar=True,require_admin=False)
        try:
            client.call('lovelace/config/save',url_path=path,config=config)
            stored=client.call('lovelace/config',url_path=path)
            if not isinstance(stored,dict) or stored.get('views')!=config['views']:raise PublishError('Verifica contenuto non riuscita')
        except Exception as exc:raise PublishError(f'Pagina {path} creata ma contenuto non verificato: {str(exc)[:100]}') from exc
    return {'created':True,'url_path':path}
