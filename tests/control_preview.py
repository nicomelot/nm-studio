"""Local UI QA against synthetic project data; never connects to Home Assistant.

python tests/control_preview.py --port 8766
This fixture is not copied into the add-on image.
"""
import argparse
import copy
import sys
import tempfile
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
    ha.config['location_name']='Laboratorio QA (dati sintetici)'
    original=ha.call
    def call(method,**params):
        result=original(method,**params)
        if method=='call_service':
            state=next(s for s in ha.states if s['entity_id']==params['target']['entity_id'])
            service=params['service'];data=params['service_data']
            if service=='turn_on':state['state']='on'
            elif service=='turn_off':state['state']='off'
            elif service=='set_temperature':state['attributes']['temperature']=data['temperature']
        return result
    ha.call=call
    def save(payload):
        current.clear();current.update(copy.deepcopy({k:v for k,v in payload.items() if k!='confirm'}));return {'saved':True}
    control_engine.save_layout=save
    with tempfile.TemporaryDirectory() as root:
        engine=control_engine.ControlEngine(root,lambda:copy.deepcopy(current),lambda:ha)
        engine.health={'running':False,'last_check':None,'error':'Anteprima QA: programmatore disattivato, servizi HA simulati'}
        bridge.CONTROL=engine
        engine.features.start()
        class Local(bridge.Handler):
            def do_GET(self):
                self.client_address=(bridge.INGRESS_PROXY,self.client_address[1]);super().do_GET()
            def do_POST(self):
                self.client_address=(bridge.INGRESS_PROXY,self.client_address[1]);super().do_POST()
        print(f'QA only: http://127.0.0.1:{args.port}',flush=True)
        ThreadingHTTPServer(('127.0.0.1',args.port),Local).serve_forever()
