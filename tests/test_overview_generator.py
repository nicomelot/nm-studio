import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_control_engine import layout,FakeHA
from nm_bridge import overview_generator as o, control_engine as m

class OverviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.layout=layout()
  class HA(FakeHA):
   def __init__(self):super().__init__();self.dashboards={}
   def call(self,method,**kw):
    if method=='lovelace/dashboards/list':return [{'url_path':p,'title':c.get('title',p),'mode':'storage'} for p,c in self.dashboards.items()]
    if method=='lovelace/config':return copy.deepcopy(self.dashboards[kw['url_path']])
    if method=='lovelace/dashboards/create':self.dashboards[kw['url_path']]={'views':[]};self.calls.append((method,kw));return {}
    if method=='lovelace/config/save':self.dashboards[kw['url_path']]=copy.deepcopy(kw['config']);self.calls.append((method,kw));return {}
    return super().call(method,**kw)
  self.ha=HA();self.engine=m.ControlEngine(self.tmp.name,lambda:self.layout,lambda:self.ha)
  self.payload=dict(confirm=True,project=self.layout['project'],fingerprint=m.digest(self.layout),revision=0,url_path='nm-studio-casa-test',title='Casa',entities=[w['entity_id'] for w in self.layout['widgets']],plans=[],operation='preview')
  self.addCleanup(patch.stopall);patch.object(o,'prepare').start();patch.object(o,'install_resource').start()
 def preview(self,**kw):return o.integration(self.engine,{**self.payload,**kw})
 def apply(self,**kw):
  p=self.preview(**kw);return self.preview(**kw,operation='apply',expected_fingerprint=p['fingerprint'])
 def test_preview_readonly_create_idempotent_and_standard_cards(self):
  self.preview();self.assertEqual(self.ha.dashboards,{})
  self.apply();self.assertTrue(self.preview()['unchanged']);self.assertFalse(self.ha.writes())
  cards=self.ha.dashboards[self.payload['url_path']]['views'][0]['sections'][0]['cards'];self.assertEqual(cards[1]['grid_options']['rows'],'auto')
 def test_absent_entities_excluded_and_forged_rejected(self):
  self.ha.states.pop();listed=self.preview(operation='list');self.assertEqual(len(listed['devices']),2);self.assertEqual(listed['excluded'],1)
  with self.assertRaisesRegex(ValueError,'non esiste'):self.preview()
  self.assertEqual(self.ha.dashboards,{})
 def test_manual_edit_and_deleted_views_survive_updates(self):
  self.apply();current=self.ha.dashboards[self.payload['url_path']];current['views'][0]['title']='Personalizzata';current['views'][0]['sections'][0]['cards'].append({'type':'markdown','content':'Mia card'})
  before=copy.deepcopy(current);self.layout['widgets'][0]['name']='Nuovo nome';self.payload['fingerprint']=m.digest(self.layout)
  self.assertEqual(self.preview()['preserved'],['Personalizzata']);self.apply();self.assertEqual(current,before);self.assertEqual(self.ha.dashboards[self.payload['url_path']],before)
  self.ha.dashboards[self.payload['url_path']]['views']=[]
  with self.assertRaisesRegex(ValueError,'Nessuna vista'):self.apply()
 def test_stale_preview_and_previous_unmanaged_dashboard(self):
  self.apply();p=self.preview();self.ha.dashboards[self.payload['url_path']]['title']='Manuale'
  with self.assertRaisesRegex(ValueError,'Anteprima cambiata'):self.preview(operation='apply',expected_fingerprint=p['fingerprint'])
  self.payload['url_path']='plancia-esistente';self.ha.dashboards['plancia-esistente']={'views':[{'path':'mia','cards':[{'type':'markdown','content':'Originale'}]}]};self.apply()
  self.assertEqual(self.ha.dashboards['plancia-esistente']['views'][0]['cards'][0]['content'],'Originale')
  self.assertTrue(list((Path(self.tmp.name)/'nm_overview_backups').glob('plancia-esistente-*.json')))
 def test_schemas_only_link_to_existing_views_and_missing_entities_are_documentation(self):
  plan={'id':'plant','name':'Centrale','kind':'schematic','points':[{'label':'Pompa','x':20,'y':30,'symbol':'pump','device':'missing'}],'pipes':[]}
  self.engine.features.diagram_path(self.layout['project']).write_text(json.dumps({'plans':[plan]}))
  self.payload['plans']=['plant'];self.apply();current=self.ha.dashboards[self.payload['url_path']];self.assertEqual(len(current['views']),2)
  self.assertEqual(current['views'][1]['cards'][0]['points'][0]['entity'],'')
  current['views'].pop();self.apply();current=self.ha.dashboards[self.payload['url_path']]
  self.assertEqual(len(current['views']),1);self.assertNotIn('navigation_path',json.dumps(current))
 def test_empty_and_invalid_selection_blocked(self):
  for extra in [{'entities':[]},{'plans':['missing']},{'url_path':'../bad'},{'entities':['light.nm_lab_lamp']*2}]:
   with self.assertRaises(ValueError):self.preview(**extra)
  self.assertEqual(self.ha.dashboards,{})
