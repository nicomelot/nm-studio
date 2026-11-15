import copy
import unittest
from nm_bridge.control_network import sources, status
import test_control_features as fixtures


class NetworkTests(unittest.TestCase):
    setUp = fixtures.FeatureTests.setUp
    ctx = fixtures.FeatureTests.ctx
    def test_network_roundtrip_validation_and_project_scope(self):
        plan={'id':'net','kind':'floorplan','name':'Network','background':None,'points':[{'id':'a','symbol':'data','label':'Outlet','x':30,'y':50,'device':'','technical':{'rack':'A','patch_panel':'P1','switch':'USW','switch_port':'2'},'network':{'entity':'sensor.port','switch_id':'device1','mode':'speed'}}]}
        archive=self.f.diagrams(self.ctx())
        self.f.save_diagrams(self.ctx(plans=[plan],diagram_fingerprint=archive['fingerprint']))
        saved=self.f.diagrams(self.ctx());self.assertEqual(saved['plans'][0]['points'][0]['network'],plan['points'][0]['network'])
        for bad in [{'entity':'switch.poe'},{'simulation':'up','entity':'sensor.port'},{'mode':'arbitrary'},{'entity':'sensor.x','extra':'x'}]:
            edited=copy.deepcopy(plan);edited['points'][0]['network']=bad
            with self.assertRaises(ValueError):self.f.save_diagrams(self.ctx(plans=[edited],diagram_fingerprint=saved['fingerprint']))
        self.assertEqual(self.ha.writes(),[])
        self.layout['project']='b'*64
        self.assertEqual(self.f.diagrams(self.ctx())['plans'],[])

    def test_inventory_uses_unifi_registry_and_is_read_only(self):
        original=self.ha.call
        def call(method,**kw):
            if method=='config/device_registry/list':return [{'id':'u','name':'Switch'},{'id':'other','name':'Other'}]
            if method=='config/entity_registry/list':return [{'entity_id':'sensor.port','device_id':'u','platform':'unifi'},{'entity_id':'switch.poe','device_id':'u','platform':'unifi'},{'entity_id':'sensor.other','device_id':'other','platform':'mqtt'}]
            return original(method,**kw)
        self.ha.call=call
        result=sources(self.engine,self.ctx())
        self.assertEqual(len(result['devices']),1)
        self.assertEqual([e['id'] for e in result['devices'][0]['entities']],['sensor.port'])
        self.assertEqual(self.ha.writes(),[])
        with self.assertRaises(ValueError):sources(self.engine,{**self.ctx(),'project':'wrong'})


class NetworkStatusTests(unittest.TestCase):
    def test_unknown_is_not_disconnected(self):
        self.assertEqual(status(None),'Non disponibile')
        self.assertEqual(status({'state':'unavailable'},'speed'),'Non disponibile')
        self.assertEqual(status({'state':'0'},'speed'),'Scollegata')
        self.assertEqual(status({'state':'1000'},'speed'),'Collegata')
