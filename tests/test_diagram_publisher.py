import tempfile
import unittest
from pathlib import Path
from nm_bridge.diagram_publisher import generate, publish
class DiagramPublisherTests(unittest.TestCase):
    def plan(self):
        return {'name':'House','kind':'floorplan','background':'data:image/png;base64,x','points':[{'label':'ECG','id':'a','symbol':'dali','x':25,'y':30,'device':'d','technical':{'dali_address':'12','dali_groups':'1, 2'},'notes':'{{ states }} <script>x</script>'},{'label':'RJ45','id':'b','symbol':'data','x':50,'y':70,'device':'','technical':{'rack':'A'}}]}
    def test_card_preserves_popup_fields_coordinates_and_bindings(self):
        result=generate(self.plan(),[{'id':'d','entity_id':'light.demo'}],'nm-studio-map')
        self.assertEqual(len(result['views']),1)
        card=result['views'][0]['cards'][0];self.assertEqual(card['type'],'custom:nm-floorplan-card')
        self.assertEqual(card['points'][0]['entity'],'light.demo');self.assertEqual(card['points'][1]['entity'],'')
        self.assertEqual(card['points'][0]['x'],25);self.assertIn(['Indirizzo ECG','12'],card['points'][0]['rows'])
    def test_create_preview_update_backup_and_stale_guard(self):
        class Client:
            def __init__(self):self.calls=[];self.paths=[];self.config=None
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def call(self,method,**kw):
                self.calls.append(method)
                if method=='lovelace/dashboards/list':return self.paths
                if method=='lovelace/resources':return []
                if method=='lovelace/config/save':self.config=kw['config']
                if method=='lovelace/config':return self.config
        c=Client();payload={'confirm':True,'title':'House','url_path':'nm-studio-map'}
        with tempfile.TemporaryDirectory() as root:
            run=lambda data:publish(data,self.plan(),[],lambda:c,root,root+'/backups')
            self.assertTrue(run(payload)['created']);self.assertTrue(list(Path(root).rglob('*.js')))
            c.paths=[{'url_path':'nm-studio-map'}];c.calls=[]
            with self.assertRaises(ValueError):run(payload)
            self.assertNotIn('lovelace/config/save',c.calls)
            preview=run({**payload,'update_existing':True,'preview':True})
            self.assertNotIn('lovelace/config/save',c.calls)
            with self.assertRaises(ValueError):run({**payload,'update_existing':True,'existing_fingerprint':'stale'})
            self.assertTrue(run({**payload,'update_existing':True,'existing_fingerprint':preview['existing_fingerprint']})['updated'])
            self.assertEqual(len(list((Path(root)/'backups').glob('*.json'))),1)
            self.assertFalse(any('service' in s for s in c.calls))
