import copy
import tempfile
import time
import unittest
from unittest.mock import patch
from nm_bridge import control_engine as m
from test_control_engine import FakeHA, layout

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.layout=layout();self.ha=FakeHA()
        self.ha.states += [{'entity_id':'sensor.supply','state':'42.5','attributes':{'device_class':'temperature','unit_of_measurement':'°C'}},{'entity_id':'switch.test','state':'off','attributes':{}}]
        self.engine=m.ControlEngine(self.tmp.name,lambda:copy.deepcopy(self.layout),lambda:self.ha)
        self.f=self.engine.features
    def ctx(self,**kw):
        return dict(confirm=True,project=self.layout['project'],fingerprint=m.digest(self.layout),revision=self.engine.read()['revision'],**kw)
    def widget(self,kind='momentary',entity='switch.test'):
        self.f.add_widget(self.ctx(type=kind,entity_id=entity,name='Test',room='Lab'))
        return m.binding(self.f.widgets(self.layout['project'])[-1])
    def press(self,token='test',pressed=True,device=None):
        return self.f.hold(self.ctx(token=token,pressed=pressed,device=device or self.key))
    def test_widget_scope_temperature_and_no_commands_on_add(self):
        before=copy.deepcopy(self.layout)
        self.widget('temperature','sensor.supply')
        snap=self.engine.snapshot();self.assertEqual(snap['devices'][-1]['state'],'42.5')
        self.assertEqual(snap['devices'][-1]['attributes']['unit_of_measurement'],'°C')
        self.assertEqual(snap['devices'][-1]['actions'],[])
        self.assertEqual(self.layout,before);self.assertEqual(self.ha.writes(),[])
        with self.assertRaises(ValueError):self.widget('temperature','switch.test')
        self.layout['project']='b'*64
        self.assertEqual(len(self.engine.snapshot()['devices']),3)
    def test_momentary_press_release_order_and_replay(self):
        self.key=self.widget();self.press();self.press(pressed=False)
        self.assertEqual([x['service'] for x in self.ha.writes()],['turn_on','turn_off'])
        self.press();self.press(pressed=False)
        self.assertEqual(len(self.ha.writes()),2)
        self.press(token='overtaken',pressed=False);self.press(token='overtaken')
        self.assertEqual(len(self.ha.writes()),2)
    def test_timeout_restart_and_reset_retry(self):
        self.key=self.widget();self.press()
        self.ha.fail_send=2
        self.f.release_due(now=time.time()+11)
        self.assertTrue(self.f.last_release_error)
        self.ha.fail_send=None
        other=m.ControlEngine(self.tmp.name,lambda:copy.deepcopy(self.layout),lambda:self.ha)
        other.features.release_due(recover=True)
        with other.db() as db:self.assertEqual(db.execute('SELECT status FROM holds').fetchone()[0],'closed')
        self.assertEqual(self.ha.writes()[-1]['service'],'turn_off')
    def test_release_survives_layout_changes_and_press_requires_guard(self):
        self.key=self.widget()
        with self.assertRaises(ValueError):self.f.hold({**self.ctx(token='bad',device=self.key,pressed=True),'confirm':False})
        self.press();self.layout['project']='b'*64
        self.f.hold(dict(confirm=True,project='a'*64,device=self.key,token='test',pressed=False))
        self.assertEqual(self.ha.writes()[-1]['service'],'turn_off')
    def test_rejects_parallel_presses_and_nonzero_initial_state(self):
        self.key=self.widget();self.press()
        with self.assertRaises(ValueError):self.press(token='other')
        self.press(pressed=False);self.ha.states[-1]['state']='on'
        with self.assertRaises(ValueError):self.press(token='other')
    def test_diagrams_preserve_coordinates_and_reject_stale_or_cross_project_links(self):
        read=self.f.diagrams(self.ctx())
        plan={'id':'p','kind':'schematic','name':'Plant','background':None,'points':[{'id':'v','label':'Valve','symbol':'valve','device':m.binding(self.layout['widgets'][0]),'x':25.125,'y':75.75}]}
        payload=self.ctx(plans=[plan],diagram_fingerprint=read['fingerprint'])
        self.f.save_diagrams(payload);saved=self.f.diagrams(self.ctx())
        self.assertEqual(saved['plans'],[plan]);self.assertEqual(self.ha.writes(),[])
        with self.assertRaises(ValueError):self.f.save_diagrams(payload)
        bad=copy.deepcopy(plan);bad['points'][0]['x']=float('nan')
        with self.assertRaises(ValueError):self.f.save_diagrams(self.ctx(plans=[bad],diagram_fingerprint=saved['fingerprint']))
        self.layout['project']='b'*64;self.assertEqual(self.f.diagrams(self.ctx())['plans'],[])
        bad['points'][0].update(x=10,device='unknown')
        with self.assertRaises(ValueError):self.f.save_diagrams(self.ctx(plans=[bad],diagram_fingerprint=self.f.diagrams(self.ctx())['fingerprint']))
    def test_pdf_validation_before_converter(self):
        with patch('nm_bridge.control_features.subprocess.run') as run:
            with self.assertRaises(ValueError):self.f.background(self.ctx(data='YWJj',page=1))
            run.assert_not_called()

    def test_temperature_thresholds_roundtrip_and_reject_invalid_ranges(self):
        point={'id':'s','label':'Supply','symbol':'temperature','device':'','x':50,'y':50,'temp_low':35,'temp_high':65}
        plan={'id':'p','kind':'schematic','name':'Plant','background':None,'points':[point]}
        def save():
            return self.f.save_diagrams(self.ctx(plans=[plan],diagram_fingerprint=self.f.diagrams(self.ctx())['fingerprint']))
        save()
        self.assertEqual(self.f.diagrams(self.ctx())['plans'][0]['points'][0],point)
        for low,high in [(65,35),(35,35),(float('nan'),65),(-101,65),(35,301),('35',65),(True,65)]:
            point.update(temp_low=low,temp_high=high)
            with self.assertRaises(ValueError):save()

    def test_technical_layers_symbols_notes_and_editable_pipes(self):
        from nm_bridge.control_features import SYMBOLS
        plan={'id':'tech','kind':'floorplan','name':'Technical','background':None,'points':[{'id':f'p{i}','symbol':s,'label':s,'device':'','x':20,'y':30,'layer':'dali','notes':'ECG 05 / rack A'} for i,s in enumerate(sorted(SYMBOLS))],'pipes':[{'id':'supply','label':'Mandata','color':'#EF4444','width':5,'xy':[[10,20],[80,20],[80,70]]}]}
        read=self.f.diagrams(self.ctx())
        self.f.save_diagrams(self.ctx(plans=[plan],diagram_fingerprint=read['fingerprint']))
        saved=self.f.diagrams(self.ctx());result=saved['plans'][0]
        self.assertEqual(result['points'],plan['points']);self.assertEqual(result['pipes'][0]['color'],'#ef4444')
        self.assertEqual(self.ha.writes(),[])
        for change in [{'width':True},{'width':15},{'color':'url(x)'},{'xy':[[0,0]]},{'xy':[[0,0],[101,0]]},{'xy':[[0,0],[float('nan'),0]]}]:
            bad=copy.deepcopy(plan);bad['pipes'][0].update(change)
            with self.assertRaises(ValueError):self.f.save_diagrams(self.ctx(plans=[bad],diagram_fingerprint=saved['fingerprint']))
        for change in [{'layer':'invalid'},{'notes':'x'*501}]:
            bad=copy.deepcopy(plan);bad['points'][0].update(change)
            with self.assertRaises(ValueError):self.f.save_diagrams(self.ctx(plans=[bad],diagram_fingerprint=saved['fingerprint']))
        self.assertEqual(self.f.diagrams(self.ctx())['fingerprint'],saved['fingerprint'])
