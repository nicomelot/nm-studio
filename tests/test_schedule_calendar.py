import copy,json,tempfile,unittest
from datetime import datetime,timedelta,timezone,date
from nm_bridge import climate_cards as cards, control_engine as engine, schedule_calendar as cal
from test_control_engine import FakeHA,layout

class CalendarTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.ha=FakeHA();self.layout=layout();self.now=datetime(2026,11,16,7,0,20,tzinfo=timezone.utc)
  self.row={'project':self.layout['project'],'entity':'climate.sala','days':['input_text.d'+str(i) for i in range(7)],'commit':'input_text.c','calendar':{'profiles':{'v':['input_text.vc','input_text.vs'],'f':['input_text.fc','input_text.fs']},'today':'input_text.today','next':'input_text.next'}}
  cards.write({'a':self.row},self.tmp.name)
  for ident in self.row['days']:self.put(ident,{'v':'a'*32,'s':[['08:00',22]]})
  self.put('input_text.c',{'v':'a'*32,'enabled':True})
  self.engine=engine.ControlEngine(self.tmp.name,lambda:self.layout,lambda:self.ha)
 def put(self,ident,value,changed=None):
  self.ha.states=[s for s in self.ha.states if s['entity_id']!=ident]
  self.ha.states.append({'entity_id':ident,'state':json.dumps(value),'attributes':{},'last_changed':(changed or self.now-timedelta(days=2)).isoformat()})
 def profile(self,kind,slots,enabled=True,**extra):
  meta={'v':'b'*32,'enabled':enabled,'kind':kind,**({'start':'2026-11-16','end':'2026-11-16'} if kind=='v' else {'dates':['2026-11-16']}),**extra}
  self.put(self.row['calendar']['profiles'][kind][0],meta)
  self.put(self.row['calendar']['profiles'][kind][1],{'v':'b'*32,'s':slots})
 def physical(self):return [c for c in self.ha.writes() if c['domain']!='input_text']
 def record(self):return cards.records(self.tmp.name,self.layout,self.ha.states,engine.binding)[0]
 def test_vacation_wins_holiday_then_week_resumes_without_week_writes(self):
  before=[copy.deepcopy(s) for s in self.ha.states if s['entity_id'] in self.row['days']]
  self.profile('f',[['08:00',19]]);self.profile('v',[['08:00',17]])
  self.engine.tick(self.now);self.engine.tick(self.now)
  self.engine.tick(self.now+timedelta(days=1))
  self.assertEqual([c['service_data']['temperature'] for c in self.physical()],[17,22])
  self.assertEqual([s for s in self.ha.states if s['entity_id'] in self.row['days']],before)
  self.assertFalse(any(c['target']['entity_id'] in self.row['days'] for c in self.ha.writes()))
 def test_holiday_and_empty_vacation_and_global_pause(self):
  self.profile('f',[['08:00',19]]);self.engine.tick(self.now)
  self.assertEqual(self.physical()[0]['service_data']['temperature'],19)
  self.ha.calls=[];self.profile('v',[])
  self.engine.tick(self.now+timedelta(seconds=5));self.assertEqual(self.physical(),[])
  self.profile('v',[['08:00',17]]);self.put('input_text.c',{'v':'a'*32,'enabled':False})
  self.engine.tick(self.now);self.assertEqual(self.physical(),[])
 def test_incomplete_active_profile_blocks_instead_of_falling_back(self):
  self.profile('v',[['08:00',17]]);self.put('input_text.vs',{'v':'c'*32,'s':[['08:00',17]]})
  record=self.record();self.assertFalse(record['enabled']);self.assertIn('Ferie',record['warning'])
  self.engine.tick(self.now);self.assertEqual(self.physical(),[])
 def test_disable_does_not_replay_weekly_slot(self):
  self.profile('v',[['08:00',17]],enabled=False)
  state=next(s for s in self.ha.states if s['entity_id']=='input_text.vc');state['last_changed']=self.now.isoformat()
  self.engine.tick(self.now);self.assertEqual(self.physical(),[])
 def test_preview_and_execution_share_solar_and_date_selection(self):
  self.row['entity']='cover.nm_lab_shutter';cards.write({'a':self.row},self.tmp.name)
  for ident in self.row['days']:self.put(ident,{'v':'a'*32,'s':[['08:00','close']]})
  self.profile('v',[['sunrise:15','position:35']]);r=self.record()
  runs=[x for x in engine.occurrences(r['triggers'],self.ha.config,self.now) if x[0].date()==self.now.date()]
  self.assertEqual(len(runs),1);instant,trigger,_=runs[0]
  cal.publish_preview(r,self.ha.config,instant-timedelta(minutes=1),self.ha,self.ha.states,engine.occurrences)
  nxt=json.loads(next(c for c in self.ha.writes() if c['target']['entity_id']=='input_text.next')['service_data']['value'])
  self.assertEqual(nxt['at'],instant.isoformat());self.assertEqual(nxt['value'],'position:35')
  self.engine.tick(instant+timedelta(seconds=10));self.assertEqual(self.physical()[0]['service_data'],{'position':35})
 def test_dates_and_dst_nonexistent_time(self):
  for meta in [{'kind':'v','start':'2026-02-30','end':'2026-03-02'}, {'kind':'f','dates':['2026-12-25']*2}]:
   with self.assertRaises(ValueError):cal.validate_meta({**meta,'v':'a'*32,'enabled':True})
  calendar={'v':{'enabled':True,'start':'2026-03-29','end':'2026-03-29'}}
  trigger={'id':'v_1','days':list(range(7)),'kind':'time','time':'02:30','calendar':calendar,'profile':'v'}
  self.assertEqual(engine.occurrences([trigger],self.ha.config,datetime(2026,3,29,tzinfo=timezone.utc),horizon=1),[])
 def test_preview_paused_is_not_presented_as_active(self):
  self.put('input_text.c',{'v':'a'*32,'enabled':False});self.engine.tick(self.now)
  payload=json.loads(next(c for c in self.ha.writes() if c['target']['entity_id']=='input_text.next')['service_data']['value'])
  self.assertEqual(payload['mode'],'paused');self.assertEqual(payload['profile'],'w')
 def test_snapshot_allows_same_time_in_mutually_exclusive_profiles(self):
  self.profile('f',[['08:00',19]]);self.profile('v',[['08:00',17]])
  record=self.engine.snapshot()['records'][0]
  self.assertIsNone(record['warning'])
