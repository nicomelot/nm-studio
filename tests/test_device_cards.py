import copy,json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from pathlib import Path
from nm_bridge import climate_cards as c,control_engine as m,device_card_dashboard as d
from test_control_engine import FakeHA,layout
class DeviceWeekTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ha=FakeHA();self.layout=layout();self.engine=m.ControlEngine(self.tmp.name,lambda:self.layout,lambda:self.ha)
 def week(self,index,slots,now):
  ids=['input_text.d'+str(i) for i in range(7)];v='a'*32
  c.write({'device':{'project':self.layout['project'],'entity':self.layout['widgets'][index]['entity_id'],'days':ids,'commit':'input_text.c'}},self.tmp.name)
  self.ha.states=self.ha.states[:3]+[{'entity_id':id,'state':json.dumps({'v':v,'s':slots}),'attributes':{}} for id in ids]+[{'entity_id':'input_text.c','state':json.dumps({'v':v,'enabled':True}),'last_changed':(now-timedelta(days=1)).isoformat()}]
 def test_light_alternates_on_off_and_deduplicates(self):
  now=datetime(2026,11,16,7,0,20,tzinfo=timezone.utc);self.week(0,[['08:00','on'],['08:01','off']],now)
  self.engine.tick(now);self.engine.tick(now);self.engine.tick(now+timedelta(minutes=1))
  self.assertEqual([x['service'] for x in self.ha.writes()],['turn_on','turn_off'])
 def test_solar_events_execute_cover_actions_at_signed_offsets(self):
  now=datetime(2026,11,16,10,tzinfo=timezone.utc);self.week(1,[['sunrise:-30','open'],['sunset:20','position:35']],now)
  record=c.records(self.tmp.name,self.layout,self.ha.states,m.binding)[0]
  runs=[x for x in m.occurrences(record['triggers'],self.ha.config,now) if x[0].date()==now.date()]
  for instant,_,_ in runs:self.engine.tick(instant+timedelta(seconds=10))
  self.assertEqual([x['service'] for x in self.ha.writes()],['open_cover','set_cover_position'])
  self.assertEqual(self.ha.writes()[1]['service_data'],{'position':35})
 def test_malformed_unsupported_partial_and_paused_weeks_do_not_actuate(self):
  now=datetime(2026,11,16,7,0,20,tzinfo=timezone.utc)
  for slots in [[['08:00','temperature:20']],[['sunrise:181','on']],[['08:00','position:20']],[['08:00','on'],['08:00','off']]]:
   self.week(0,slots,now);self.engine.tick(now)
  self.assertEqual(self.ha.writes(),[])
  self.week(0,[['08:00','on']],now);self.ha.states[-1]['state']=json.dumps({'v':'b'*32,'enabled':True});self.engine.tick(now)
  self.ha.states[-1]['state']=json.dumps({'v':'a'*32,'enabled':False});self.engine.tick(now);self.assertEqual(self.ha.writes(),[])
 def test_device_helper_installation_is_idempotent(self):
  class WS:
   def __init__(self):self.calls=[]
   def call(self,method,**kw):
    self.calls.append(method)
    if method=='input_text/create':return {'id':kw['name']}
    if method=='call_service':
     assert kw['domain']=='input_text'
     return {}
    if method=='lovelace/resources':return []
    if method=='lovelace/resources/create':return {}
    raise AssertionError(method)
  ws=WS();card=c.config('a'*64,'light.nm_lab_lamp','Lamp')
  c.prepare(card,ws,self.tmp.name,self.tmp.name);c.prepare(card,ws,self.tmp.name,self.tmp.name)
  self.assertEqual(ws.calls.count('input_text/create'),17);self.assertEqual(card['type'],'custom:nm-device-card')
class DashboardIntegrationTests(unittest.TestCase):
 def test_preserves_original_preview_stale_guard_and_idempotency(self):
  with tempfile.TemporaryDirectory() as root:
   class WS:
    def __init__(self):self.config={'views':[{'title':'Originale','cards':[{'type':'markdown','content':'Personale'}]}]};self.calls=[]
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def call(self,method,**kw):
     self.calls.append(method)
     if method=='lovelace/dashboards/list':return []
     if method=='lovelace/config':return copy.deepcopy(self.config)
     if method=='lovelace/config/save':self.config=copy.deepcopy(kw['config']);return None
     raise AssertionError(method)
   ws=WS();l=layout();engine=m.ControlEngine(root,lambda:l,lambda:ws)
   payload={'confirm':True,'project':l['project'],'fingerprint':m.digest(l),'revision':0,'url_path':'lovelace','entities':['light.nm_lab_lamp','cover.nm_lab_shutter'],'operation':'preview'}
   preview=d.integration(engine,payload);self.assertNotIn('lovelace/config/save',ws.calls)
   original=copy.deepcopy(ws.config);ws.config['title']='changed'
   with self.assertRaises(ValueError):d.integration(engine,{**payload,'operation':'apply','confirm':True,'expected_fingerprint':preview['fingerprint']})
   preview=d.integration(engine,payload)
   with patch.object(d,'prepare'):
    d.integration(engine,{**payload,'operation':'apply','confirm':True,'expected_fingerprint':preview['fingerprint']})
   self.assertEqual(ws.config['views'][0],original['views'][0]);self.assertEqual(len(ws.config['views'][1]['cards']),2)
   self.assertEqual(len(list((Path(root)/'nm_dashboard_card_backups').glob('*.json'))),1)
   self.assertEqual(d.integration(engine,payload)['added'],[])
