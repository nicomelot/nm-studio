"""Local UI QA against synthetic project data; never connects to Home Assistant.

python tests/control_preview.py --port 8766
This fixture is not copied into the add-on image.
"""
import argparse
import copy
import sys
import tempfile
import queue
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'nm_bridge'))
sys.path.insert(0,str(ROOT))
import bridge
import control_engine
from test_control_engine import layout, FakeHA


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    current=layout();ha=FakeHA()
    for suffix in ('Studio', 'Camera'):
        widget=copy.deepcopy(current['widgets'][2]);widget.update(name='Termostato '+suffix, entity_id='climate.'+suffix.lower(), room='Casa / '+suffix)
        current['widgets'].append(widget);current['rooms'].append(widget['room'])
        state=copy.deepcopy(ha.states[2]);state['entity_id']=widget['entity_id'];ha.states.append(state)
    ha.states += [{'entity_id':'sensor.nm_lab_supply','state':'42.5','attributes':{'friendly_name':'Sonda mandata simulata','device_class':'temperature','unit_of_measurement':'°C'}},{'entity_id':'switch.nm_lab_pulse','state':'off','attributes':{'friendly_name':'Pulsante simulato'}}]
    for index, widget in enumerate(current['widgets']):
        state=next(s for s in ha.states if s['entity_id']==widget['entity_id'])
        widget['entity_id']=widget['entity_id'].split('.')[0]+'.nm_lab_'+current['project'][:12]+'_'+str(index)
        state['entity_id']=widget['entity_id']
    now=datetime.now(timezone.utc)
    ha.states.append({'entity_id':'sensor.decision_qa','state':'ready','attributes':{
        'decision_id':'qa-decision','simulation':True,'status':'ready','execution_enabled':False,
        'generated_at':now.isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat(),
        'summary':'Decisioni di collaudo: dati sintetici, nessun impianto reale',
        'actions':[{'action':name,'reason':reason,'explanation':'Scenario sintetico per verificare anteprima e conferma.',
                    'proposal_only':True,'requires_confirmation':True} for name,reason in [
                    ('Riduci illuminazione','Stanza simulata non occupata'),('Regola tapparella','Protezione solare simulata'),
                    ('Imposta comfort','Temperatura simulata sotto obiettivo')]]}})
    ha.states.extend([
        {'entity_id':'light.philips_demo','state':'off','attributes':{'friendly_name':'DEMO Philips','supported_color_modes':['brightness']}},
        {'entity_id':'switch.sonoff_demo','state':'off','attributes':{'friendly_name':'DEMO Sonoff'}},
        {'entity_id':'media_player.wiim_demo','state':'paused','attributes':{'friendly_name':'DEMO WiiM','supported_features':16384+1+4+8+2048,'volume_level':.2,'source_list':['Wi-Fi','Line In']}},
        {'entity_id':'event.sonoff_demo','state':'unknown','attributes':{'friendly_name':'DEMO pulsante Sonoff','event_type':'single','event_types':['single','double','hold']}}
    ])
    ha.states.append({'entity_id':'input_button.sonoff_sim','state':'unknown','attributes':{'friendly_name':'SIM Sonoff · pressione'}})
    ha.config['location_name']='Laboratorio QA (dati sintetici)'
    original=ha.call
    def call(method,**params):
        result=original(method,**params)
        if method=='call_service':
            state=next(s for s in ha.states if s['entity_id']==params['target']['entity_id'])
            service=params['service'];data=params['service_data']
            if service=='turn_on':
                state['state']='on'
                if 'brightness_pct' in data:state['attributes']['brightness']=round(data['brightness_pct']*255/100)
            elif service=='press':
                old=copy.deepcopy(state);state['state']=datetime.now(timezone.utc).isoformat()
                for client in list(clients):
                    for sid,trigger in list(client.subs.items()):
                        if trigger.get('entity_id')==state['entity_id']:
                            client.events.put({'id':sid,'type':'event','event':{'variables':{'trigger':{'from_state':old,'to_state':copy.deepcopy(state)}},'context':{'id':state['state']}}})
            elif service=='turn_off':state['state']='off'
            elif service=='volume_set':state['attributes']['volume_level']=data['volume_level']
            elif service=='media_play':state['state']='playing'
            elif service=='media_pause':state['state']='paused'
            elif service=='select_source':state['attributes']['source']=data['source']
            elif service=='volume_mute':state['attributes']['is_volume_muted']=data['is_volume_muted']
            elif service=='set_cover_position':state['attributes']['current_position']=data['position']
            elif service=='set_temperature':state['attributes']['temperature']=data['temperature']
        return result
    ha.call=call
    clients=[]
    class Session:
        def __init__(self):self.sequence=0;self.events=queue.Queue();self.subs={};self.connection=self
        def __enter__(self):clients.append(self);return self
        def __exit__(self,*args):clients.remove(self)
        def settimeout(self,value):pass
        def send(self,data):
            p=json.loads(data);self.events.put({'id':p['id'],'type':'pong'})
        def _receive(self):
            try:return self.events.get(timeout=.2)
            except queue.Empty:raise TimeoutError()
        def call(self,method,**args):
            self.sequence+=1
            if method=='config/device_registry/list':return []
            if method=='subscribe_trigger':self.subs[self.sequence]=args['trigger'];return None
            if method=='unsubscribe_events':self.subs.pop(args['subscription'],None);return None
            return ha.call(method,**args)

    def save(payload):
        current.clear();current.update(copy.deepcopy({k:v for k,v in payload.items() if k!='confirm'}));return {'saved':True}
    control_engine.save_layout=save
    with tempfile.TemporaryDirectory() as root:
        engine=control_engine.ControlEngine(root,lambda:copy.deepcopy(current),lambda:Session())
        engine.health={'running':False,'last_check':None,'error':'Anteprima QA: programmatore disattivato, servizi HA simulati'}
        bridge.CONTROL=engine
        engine.start()
        class Local(bridge.Handler):
            def do_GET(self):
                self.client_address=(bridge.INGRESS_PROXY,self.client_address[1]);super().do_GET()
            def do_POST(self):
                self.client_address=(bridge.INGRESS_PROXY,self.client_address[1]);super().do_POST()
        print(f'QA only: http://127.0.0.1:{args.port}',flush=True)
        ThreadingHTTPServer(('127.0.0.1',args.port),Local).serve_forever()
