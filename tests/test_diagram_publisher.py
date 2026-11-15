import unittest
from nm_bridge.diagram_publisher import generate, publish
class DiagramPublisherTests(unittest.TestCase):
    def plan(self):
        return {'name':'House','kind':'floorplan','background':'data:image/png;base64,x','points':[{'label':'ECG','id':'a','symbol':'dali','x':25,'y':30,'device':'d','technical':{'dali_address':'12','dali_groups':'1, 2'},'notes':'{{ states }} <script>x</script>'},{'label':'RJ45','id':'b','symbol':'data','x':50,'y':70,'device':'','technical':{'rack':'A'}}]}
    def test_native_page_has_hover_details_navigation_and_no_toggle(self):
        result=generate(self.plan(),[{'id':'d','entity_id':'light.demo'}],'nm-studio-map')
        els=result['views'][0]['cards'][0]['elements'];self.assertEqual(len(els),2)
        self.assertIn('12',els[0]['title']);self.assertEqual(els[1]['type'],'icon')
        self.assertEqual(els[0]['tap_action'],{'action':'navigate','navigation_path':'/nm-studio-map/punto-0'})
        self.assertTrue(result['views'][1]['subview']);self.assertNotIn('{{',result['views'][1]['cards'][0]['content'])
        self.assertNotIn('<script>',result['views'][1]['cards'][0]['content'])
        self.assertEqual(result['views'][1]['cards'][1]['icon_tap_action']['action'],'more-info')
    def test_create_only_and_readback_verification(self):
        class Client:
            def __init__(self):self.calls=[];self.paths=[];self.config=None
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def call(self,method,**kw):
                self.calls.append(method)
                if method=='lovelace/dashboards/list':return self.paths
                if method=='lovelace/config/save':self.config=kw['config']
                if method=='lovelace/config':return self.config
        c=Client();payload={'confirm':True,'title':'House','url_path':'nm-studio-map'}
        self.assertTrue(publish(payload,self.plan(),[],lambda:c)['created'])
        self.assertFalse(any('service' in s for s in c.calls))
        c.paths=[{'url_path':'nm-studio-map'}];c.calls=[]
        with self.assertRaises(ValueError):publish(payload,self.plan(),[],lambda:c)
        self.assertEqual(c.calls,['lovelace/dashboards/list'])
        with self.assertRaises(ValueError):publish({**payload,'confirm':False},self.plan(),[],lambda:c)
