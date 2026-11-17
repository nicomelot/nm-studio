import copy
import unittest
from nm_bridge.climate_cards import provision_favorites,provision_favorite_order,key

class FavoriteTests(unittest.TestCase):
 def test_seed_existing_favorites_once_without_changing_dashboard_or_devices(self):
  project='a'*64; ident=key(project,'light.sala'); other=key(project,'cover.camera')
  original={'views':[{'path':'preferiti','sections':[{'cards':[{'type':'custom:nm-device-card','entity':'light.sala','project':project}]}]}]}
  class HA:
   def __init__(self): self.helpers=[];self.calls=[]
   def call(self,method,**args):
    self.calls.append((method,copy.deepcopy(args)))
    if method=='get_states':return []
    if method=='input_boolean/list':return copy.deepcopy(self.helpers)
    if method=='lovelace/dashboards/list':return [{'url_path':'nm-studio-casa','mode':'storage'}]
    if method=='lovelace/config':return copy.deepcopy(original)
    if method=='input_boolean/create':
     item={'id':args['name']};self.helpers.append(item);return item
    if method=='call_service':return {}
    raise AssertionError(method)
  ha=HA();data={ident:{'project':project,'entity':'light.sala'},other:{'project':project,'entity':'cover.camera'}}
  provision_favorites(ha,data);first=copy.deepcopy(ha.calls);provision_favorites(ha,data)
  writes=[a for m,a in ha.calls if m=='call_service']
  self.assertEqual(len(writes),1)
  self.assertEqual(writes[0]['domain'],'input_boolean')
  self.assertEqual(writes[0]['target'],{'entity_id':'input_boolean.nm_favorite_'+ident})
  self.assertEqual(len(ha.helpers),2)
  self.assertFalse(any(m=='lovelace/config/save' for m,a in ha.calls))
  self.assertEqual(data[ident],{'project':project,'entity':'light.sala'})
  self.assertEqual(len([1 for m,a in first if m=='input_boolean/create']),2)

 def test_order_helpers_are_idempotent_and_never_reset_saved_ranks(self):
  class HA:
   def __init__(self):self.helpers=[];self.calls=[]
   def call(self,method,**args):
    self.calls.append((method,args))
    if method=='input_number/list':return self.helpers[:]
    if method=='input_number/create':
     self.helpers.append({'id':args['name']});return self.helpers[-1]
    raise AssertionError(method)
  ha=HA();data={'a':{'project':'a'*64,'entity':'light.sala'},'invalid':{'project':'bad','entity':'light.no'}}
  provision_favorite_order(ha,data);provision_favorite_order(ha,data)
  self.assertEqual(len(ha.helpers),1)
  create=[args for method,args in ha.calls if method=='input_number/create'][0]
  self.assertEqual(create['min'],0)
  self.assertEqual(create['step'],0.000001)
  self.assertFalse(any(method=='call_service' for method,args in ha.calls))

if __name__=='__main__':unittest.main()
