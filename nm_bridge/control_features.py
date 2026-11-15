"""Project diagrams, supplementary widgets and durable momentary-button releases."""
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

try:
    from .floorplan import _image, read as legacy_plans
except ImportError:
    from floorplan import _image, read as legacy_plans

ID = re.compile(r'^[a-zA-Z0-9_-]{1,80}$')
SYMBOLS = {'pump', 'valve', 'temperature', 'boiler', 'tank', 'light', 'button', 'label'}
SYMBOLS.update({'data','dali','knx','wifi','camera','rack','outlet','spot','downlight','led-strip','pendant','wall','cover','thermostat','sensor','fan','motion','contact'})
LAYERS = {'light','dali','knx','data','wifi','camera','climate','rack','other'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ControlFeatures:
    def __init__(self, engine, binding):
        self.engine, self.binding = engine, binding
        self.hold_lock = threading.RLock()
        self.worker = None
        self.last_release_error = ''

    def widgets(self, project, raw=None):
        return (raw or self.engine.read()).get('extra_widgets', {}).get(project, [])

    def candidates(self, states):
        return [{'entity_id': s['entity_id'], 'name': s.get('attributes', {}).get('friendly_name', s['entity_id']),
                 'state': s.get('state', 'unavailable'), 'temperature':s.get('attributes',{}).get('device_class')=='temperature', 'unit': s.get('attributes', {}).get('unit_of_measurement', '')}
                for s in states if s['entity_id'].split('.')[0] in ('sensor', 'switch', 'input_boolean', 'light')]

    def add_widget(self, payload):
        e = self.engine
        with e.lock:
            layout, raw = e.layout_provider(), e.read()
            e.guard(payload, layout, raw)
            kind, entity, name, room = (payload.get(k) for k in ('type','entity_id','name','room'))
            if kind not in ('temperature', 'momentary') or not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or not isinstance(room, str) or not 1 <= len(room.strip()) <= 240:
                raise ValueError('Tipo, nome o ambiente non valido')
            with e.connection_factory() as ws:
                states = ws.call('get_states')
            state = next((s for s in states if s['entity_id'] == entity), None)
            if not state or state.get('state') in ('unavailable', 'unknown'):
                raise ValueError('Entità non disponibile')
            domain = entity.split('.')[0]
            if kind == 'temperature' and (domain != 'sensor' or state.get('attributes', {}).get('device_class') != 'temperature'):
                raise ValueError('Seleziona una sonda di temperatura Home Assistant')
            if kind == 'momentary' and domain not in ('switch','input_boolean','light'):
                raise ValueError('Il pulsante richiede una entità binaria (luce o interruttore)')
            widgets = raw.setdefault('extra_widgets', {}).setdefault(layout['project'], [])
            if len(widgets) >= 100 or any(w['type']==kind and w['entity_id']==entity for w in widgets):
                raise ValueError('Widget già presente o limite raggiunto')
            widgets.append({'type':kind, 'name':name.strip(), 'room':room.strip(), 'entity_id':entity, 'fields':{}})
            raw['revision'] += 1
            e.write(raw)
            return {'saved':True}

    def hold_db(self):
        return self.engine.db()

    def reset(self, token):
        # The entity is taken from the durable lease, never from the release request.
        with self.hold_lock:
            with self.hold_db() as db:
                row = db.execute('SELECT entity,status FROM holds WHERE token=?',(token,)).fetchone()
            if not row or row[1] == 'closed':
                return
            entity = row[0]
            try:
                with self.engine.connection_factory() as ws:
                    ws.call('call_service', domain=entity.split('.')[0], service='turn_off', target={'entity_id':entity}, service_data={})
                with self.hold_db() as db:
                    db.execute("UPDATE holds SET status='closed' WHERE token=?",(token,))
                self.last_release_error = ''
            except Exception:
                self.last_release_error = 'Reset a 0 non confermato: nuovo tentativo al ripristino del collegamento.'
                with self.hold_db() as db:
                    db.execute('UPDATE holds SET expires=? WHERE token=?',(time.time()+2,token))
                raise ValueError(self.last_release_error) from None

    def hold(self, payload):
        e = self.engine
        token, device, project = payload.get('token'), payload.get('device'), payload.get('project')
        if payload.get('confirm') is not True or not isinstance(token,str) or not ID.fullmatch(token) or not isinstance(device,str) or type(payload.get('pressed')) is not bool or not isinstance(project,str):
            raise ValueError('Comando pulsante non valido')
        with self.hold_lock:
            with self.hold_db() as db:
                previous = db.execute('SELECT project,device,status FROM holds WHERE token=?',(token,)).fetchone()
            if previous and previous[:2] != (project,device):
                raise ValueError('Identità del pulsante cambiata')
            if not payload['pressed']:
                # A release that overtakes its press must prevent the late press.
                with self.hold_db() as db:
                    db.execute("INSERT OR IGNORE INTO holds VALUES(?,?,?,?,?,?,'closed')",(token,project,device,'',time.time(),time.time()))
                self.reset(token)
                return {'released':True}
            if previous:
                return {'duplicate':True, 'released':previous[2]=='closed'}
            with e.lock:
                layout, raw = e.layout_provider(), e.read()
                e.guard(payload,layout,raw)
                matches = [w for w in self.widgets(project,raw) if self.binding(w)==device and w['type']=='momentary']
                if len(matches)!=1:
                    raise ValueError('Pulsante non trovato')
                entity=matches[0]['entity_id']
                with self.hold_db() as db:
                    if db.execute("SELECT 1 FROM holds WHERE entity=? AND status!='closed'",(entity,)).fetchone():
                        raise ValueError('Pulsante già premuto: attendi il rilascio')
                with e.connection_factory() as ws:
                    state=next((s for s in ws.call('get_states') if s['entity_id']==entity),None)
                    if not state or state.get('state')!='off':
                        raise ValueError('Il comando deve essere disponibile e a 0 prima della pressione')
                    now=time.time()
                    with self.hold_db() as db:
                        db.execute("INSERT INTO holds VALUES(?,?,?,?,?,?,'active')",(token,project,device,entity,now+10,now))
                    try:
                        ws.call('call_service',domain=entity.split('.')[0],service='turn_on',target={'entity_id':entity},service_data={})
                    except Exception:
                        self.reset(token)
                        raise ValueError('Pressione non confermata: richiesto reset a 0') from None
            return {'pressed':True,'max_seconds':10}

    def release_due(self, now=None, recover=False):
        with self.hold_lock:
            with self.hold_db() as db:
                rows=db.execute("SELECT token FROM holds WHERE status!='closed' AND (? OR expires<=?)",(recover,now or time.time())).fetchall()
                db.execute("DELETE FROM holds WHERE status='closed' AND created<?",(time.time()-86400,))
            for (token,) in rows:
                try:self.reset(token)
                except ValueError:pass

    def start(self):
        if self.worker and self.worker.is_alive():return
        def run():
            self.release_due(recover=True)
            while not self.engine.stop_event.wait(.25):
                try:self.release_due()
                except Exception:self.last_release_error='Verifica il collegamento: reset del pulsante in attesa.'
        self.worker=threading.Thread(target=run,name='nm-button-reset',daemon=True);self.worker.start()

    def diagram_path(self, project):
        if not re.fullmatch('[0-9a-f]{64}',project or ''):raise ValueError('Seleziona prima un progetto')
        return self.engine.root / ('diagrams_'+project+'.json')

    def diagrams(self, payload):
        e=self.engine
        with e.lock:
            layout,raw=e.layout_provider(),e.read();e.guard(payload,layout,raw)
            path=self.diagram_path(layout['project'])
            saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'plans':[]}
            result={'plans':saved['plans'],'fingerprint':fingerprint(saved)}
            try:result['legacy']=legacy_plans()['plans']
            except (ValueError,OSError):result['legacy']=[]
            return result

    def save_diagrams(self,payload):
        e=self.engine
        with e.lock:
            current=self.diagrams(payload)
            if current['fingerprint']!=payload.get('diagram_fingerprint'):raise ValueError('Schemi modificati altrove: riapri prima di salvare')
            plans=payload.get('plans')
            if not isinstance(plans,list) or len(plans)>15:raise ValueError('Massimo 15 schemi per progetto')
            layout=e.layout_provider();known={self.binding(w) for w in layout['widgets']+self.widgets(layout['project'])}
            clean=[];ids=set()
            for p in plans:
                if not isinstance(p,dict) or not isinstance(p.get('id'),str) or not ID.fullmatch(p['id']) or p['id'] in ids:raise ValueError('Identificativo schema non valido')
                ids.add(p['id'])
                name=p.get('name');kind=p.get('kind')
                if not isinstance(name,str) or not 1<=len(name.strip())<=80 or kind not in ('schematic','floorplan'):raise ValueError('Nome o tipo schema non valido')
                image=_image(p.get('background'))
                points=p.get('points',[])
                if not isinstance(points,list) or len(points)>300:raise ValueError('Troppi componenti')
                pins=[];point_ids=set()
                for t in points:
                    if not isinstance(t,dict) or not isinstance(t.get('id'),str) or not ID.fullmatch(t['id']) or t['id'] in point_ids:raise ValueError('Componente non valido')
                    point_ids.add(t['id'])
                    if t.get('symbol') not in SYMBOLS or not isinstance(t.get('label'),str) or not 1<=len(t['label'].strip())<=65:raise ValueError('Simbolo o nome non valido')
                    if any(type(t.get(v)) not in (int,float) or not math.isfinite(t[v]) or not 0<=t[v]<=100 for v in ('x','y')):raise ValueError('Posizione non valida')
                    target=t.get('device','')
                    # Keep stale links visible; only newly introduced links must exist.
                    old={(q['id'],v['id'],v.get('device','')) for q in current['plans'] for v in q['points']}
                    if target and target not in known and (p['id'],t['id'],target) not in old:raise ValueError('Dispositivo non presente nel progetto')
                    pin={'id':t['id'],'symbol':t['symbol'],'label':t['label'].strip(),'device':target,'x':round(t['x'],3),'y':round(t['y'],3)}
                    if 'layer' in t:
                        if t['layer'] not in LAYERS:raise ValueError('Livello tecnico non valido')
                        pin['layer']=t['layer']
                    if 'notes' in t:
                        if not isinstance(t['notes'],str) or len(t['notes'])>500:raise ValueError('Note massimo 500 caratteri')
                        pin['notes']=t['notes'].strip()
                    if 'temp_low' in t or 'temp_high' in t:
                        low,high=t.get('temp_low',18),t.get('temp_high',28)
                        if any(type(v) not in (int,float) or not math.isfinite(v) or not -100<=v<=300 for v in (low,high)) or low>=high:
                            raise ValueError('Soglie temperatura: la soglia bassa deve essere inferiore a quella alta (da -100 a 300 °C)')
                        pin.update(temp_low=low,temp_high=high)
                    pins.append(pin)
                plan={'id':p['id'],'name':name.strip(),'kind':kind,'background':image,'points':pins}
                if 'pipes' in p:
                    pipes=p['pipes'];pipe_ids=set();paths=[]
                    if not isinstance(pipes,list) or len(pipes)>100:raise ValueError('Massimo 100 tubazioni per schema')
                    for pipe in pipes:
                        if not isinstance(pipe,dict) or not isinstance(pipe.get('id'),str) or not ID.fullmatch(pipe['id']) or pipe['id'] in pipe_ids:raise ValueError('Identificativo tubazione non valido')
                        pipe_ids.add(pipe['id'])
                        label,color,width,xy=(pipe.get(k) for k in ('label','color','width','xy'))
                        if not isinstance(label,str) or not 1<=len(label.strip())<=65:raise ValueError('Nome tubazione non valido')
                        if not isinstance(color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',color):raise ValueError('Colore tubazione non valido')
                        if type(width) not in (int,float) or not math.isfinite(width) or not 2<=width<=12:raise ValueError('Spessore tubazione da 2 a 12')
                        if not isinstance(xy,list) or not 2<=len(xy)<=64:raise ValueError('Ogni tubazione richiede da 2 a 64 punti')
                        if any(not isinstance(v,list) or len(v)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=100 for n in v) for v in xy):raise ValueError('Posizione tubazione non valida')
                        paths.append({'id':pipe['id'],'label':label.strip(),'color':color.lower(),'width':width,'xy':[[round(n,3) for n in v] for v in xy]})
                    plan['pipes']=paths
                clean.append(plan)
            data={'plans':clean};encoded=json.dumps(data,ensure_ascii=False)
            if len(encoded.encode())>20*1024*1024:raise ValueError('Archivio schemi troppo grande (20 MB)')
            path=self.diagram_path(layout['project']);path.parent.mkdir(parents=True,exist_ok=True)
            temp=None
            try:
                with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as f:
                    temp=f.name;f.write(encoded);f.flush();os.fsync(f.fileno())
                os.replace(temp,path)
            finally:
                if temp and os.path.exists(temp):os.unlink(temp)
            return {'saved':True,'fingerprint':fingerprint(data)}

    def background(self,payload):
        e=self.engine;e.guard(payload,e.layout_provider(),e.read())
        data=payload.get('data','');page=payload.get('page',1)
        if not isinstance(data,str) or len(data)>16*1024*1024 or type(page)!=int or not 1<=page<=100:raise ValueError('PDF massimo 12 MB; pagina da 1 a 100')
        try:raw=base64.b64decode(data,validate=True)
        except Exception:raise ValueError('PDF non valido') from None
        if not raw.startswith(b'%PDF-'):raise ValueError('Il file non è un PDF')
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.pdf';source.write_bytes(raw);output=Path(folder)/'page'
            try:subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-scale-to','2000','-jpeg','-jpegopt','quality=85',str(source),str(output)],check=True,timeout=25,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except (OSError,subprocess.SubprocessError):raise ValueError('Impossibile leggere questa pagina PDF; verifica il numero o carica PNG/JPG') from None
            image=output.with_suffix('.jpg')
            if not image.exists():raise ValueError('Pagina PDF non presente')
            return {'image':_image('data:image/jpeg;base64,'+base64.b64encode(image.read_bytes()).decode())}
