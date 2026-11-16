import copy
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from nm_bridge import climate_cards as c, control_engine as m
from test_control_engine import FakeHA,layout

class ClimateCardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ha=FakeHA();self.layout=layout();self.engine=m.ControlEngine(self.tmp.name,lambda:copy.deepcopy(self.layout),lambda:self.ha)
        self.now=datetime(2026,11,16,7,0,20,tzinfo=timezone.utc)
        self.ids=['input_text.day'+str(i) for i in range(7)]
        self.row={'project':self.layout['project'],'entity':'climate.sala','days':self.ids,'commit':'input_text.commit'}
        c.write({'abc':self.row},self.tmp.name)
        self.version='a'*32
        for eid in self.ids:self.ha.states.append({'entity_id':eid,'state':json.dumps({'v':self.version,'s':[['08:00',22]]}),'attributes':{}})
        self.ha.states.append({'entity_id':'input_text.commit','state':json.dumps({'v':self.version,'enabled':True}),'last_changed':(self.now-timedelta(minutes=2)).isoformat(),'attributes':{}})
    def test_week_runs_in_existing_engine_and_is_deduplicated(self):
        self.engine.tick(self.now);self.engine.tick(self.now)
        self.assertEqual(len(self.ha.writes()),1)
        self.assertEqual(self.ha.writes()[0]['service'],'set_temperature')
        self.assertEqual(self.ha.writes()[0]['service_data'],{'temperature':22})
        snap=self.engine.snapshot();self.assertEqual(snap['records'][0]['source'],'ha_card')
    def test_partial_write_and_paused_program_never_execute(self):
        self.ha.states[-1]['state']=json.dumps({'v':'b'*32,'enabled':True})
        self.engine.tick(self.now);self.assertEqual(self.ha.writes(),[])
        self.ha.states[-1]['state']=json.dumps({'v':self.version,'enabled':False})
        self.engine.tick(self.now);self.assertEqual(self.ha.writes(),[])
    def test_invalid_temperature_and_other_project_are_not_executed(self):
        self.ha.states[3]['state']=json.dumps({'v':self.version,'s':[['08:00',1000]]})
        self.engine.tick(self.now);self.assertEqual(self.ha.writes(),[])
        self.layout['project']='b'*64
        self.assertEqual(c.records(self.tmp.name,self.layout,self.ha.states,m.binding),[])
    def test_activation_does_not_replay_previous_slot(self):
        self.ha.states[-1]['last_changed']=self.now.isoformat()
        self.engine.tick(self.now);self.assertEqual(self.ha.writes(),[])
    def test_existing_nm_schedule_takes_precedence(self):
        record={'id':'nm','kind':'schedule','name':'Existing','room':'Casa','enabled':True,'activated_at':(self.now-timedelta(days=1)).isoformat(),'actions':[{'device':m.binding(self.layout['widgets'][2]),'action':'temperature','value':18}],'triggers':[{'id':'t','kind':'time','time':'08:00','days':[0]}]}
        self.engine.write({'version':1,'revision':0,'projects':{self.layout['project']:[record]}})
        self.engine.tick(self.now);self.assertEqual(len(self.ha.writes()),1);self.assertEqual(self.ha.writes()[0]['service_data'],{'temperature':18})
    def test_provisioning_is_idempotent_preserves_manual_options_and_never_commands(self):
        class Client:
            def __init__(self):self.created=[]
            def call(self,method,**args):
                if method=='input_text/create':self.created.append(args);return {'id':args['name']}
                if method=='call_service':
                    assert args['domain']=='input_text'
                    return {}
                if method=='lovelace/resources':return []
                if method=='lovelace/resources/create':return {}
                raise AssertionError(method)
        ws=Client();card=c.config('b'*64,'climate.other','Other');card['filter_alarm']='binary_sensor.manual'
        with tempfile.TemporaryDirectory() as root:
            c.prepare(card,ws,root,root);c.prepare(card,ws,root,root)
            self.assertEqual(len(ws.created),17);self.assertEqual(len(card['schedule']['days']),7)
            self.assertEqual(card['filter_alarm'],'binary_sensor.manual')
            self.assertTrue((Path(root)/'www/nm-control/nm-climate-card-5.40.0.js').exists())

