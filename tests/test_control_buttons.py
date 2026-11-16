import copy
import tempfile
import unittest
import threading
from unittest.mock import patch
from nm_bridge.control_engine import ControlEngine, binding, digest
from tests.test_control_engine import FakeHA, layout


class ButtonHA(FakeHA):
    sequence=0
    def call(self, method, **args):
        self.sequence+=1
        if method=='config/device_registry/list':return [{'id':'sonoff','name':'Sonoff test'}]
        if method=='device_automation/trigger/list':return [{'platform':'device','domain':'zha','device_id':'sonoff','type':'remote_button_short_press','subtype':'button'}]
        if method in ('subscribe_trigger','unsubscribe_events'):return None
        return super().call(method,**args)


class ButtonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.layout=layout();self.ha=ButtonHA()
        self.ha.states += [{'entity_id':'event.sonoff','state':'old','attributes':{'event_types':['single','double'],'event_type':'single'}},
                           {'entity_id':'input_button.demo','state':'unknown','attributes':{}}]
        self.e=ControlEngine(self.tmp.name,lambda:copy.deepcopy(self.layout),lambda:self.ha)
        self.e.save(self.ctx(record={'id':'scene','name':'Test','kind':'scene','actions':[{'device':binding(self.layout['widgets'][0]),'action':'on'}]}))
    def ctx(self,**kw):return dict(confirm=True,project=self.layout['project'],fingerprint=digest(self.layout),revision=self.e.read()['revision'],**kw)
    def link(self,source='entity:event.sonoff'):
        option=self.e.buttons.triggers(self.ctx(source=source))['options'][0]
        p=self.ctx(name='Pulsante sala',source=source,option=option['id'],scene='scene')
        proof=self.e.buttons.review(p)
        self.assertFalse(self.ha.writes())
        self.e.buttons.review({**p,'preview_hash':proof['preview_hash']},True)
        return self.e.buttons.rules(self.e.read(),self.layout['project'])[-1]
    def event(self,old='old',new='new',kind='single'):
        return {'variables':{'trigger':{'from_state':{'state':old},'to_state':{'state':new,'attributes':{'event_type':kind}}}}}
    def test_confirm_dedup_repeat_press_and_pause(self):
        r=self.link()
        for event in (self.event(),self.event(),self.event(new='newer')):self.e.buttons.dispatch(self.layout['project'],r,event)
        self.assertEqual(len(self.ha.writes()),2)
        self.e.buttons.pause(self.ctx(id=r['id']))
        self.e.buttons.dispatch(self.layout['project'],r,self.event(new='last'))
        self.assertEqual(len(self.ha.writes()),2)
    def test_wrong_type_restore_and_wrong_project_do_not_run(self):
        r=self.link()
        for event in (self.event(kind='double'),self.event(old='unknown'),self.event(old='unavailable'),self.event(new='old')):
            self.e.buttons.dispatch(self.layout['project'],r,event)
        self.e.buttons.dispatch('other',r,self.event())
        self.assertFalse(self.ha.writes())
    def test_scene_edit_requires_review(self):
        r=self.link();raw=self.e.read();raw['projects'][self.layout['project']][0]['actions'][0]['action']='off';self.e.write(raw)
        self.e.buttons.dispatch(self.layout['project'],r,self.event())
        self.assertFalse(self.ha.writes());self.assertEqual(self.e.buttons.active(self.layout,raw),[])
    def test_native_device_and_simulated_first_press(self):
        r=self.link('device:sonoff')
        self.e.buttons.dispatch(self.layout['project'],r,{'variables':{'trigger':{'id':'0','event':{'context':{'id':'unique'}}}}})
        self.assertEqual(len(self.ha.writes()),1)
        self.ha.calls=[]
        r=self.link('entity:input_button.demo')
        self.e.buttons.dispatch(self.layout['project'],r,self.event(old='unknown'))
        self.assertEqual(len(self.ha.writes()),1)
    def test_forged_trigger_and_stale_preview(self):
        p=self.ctx(name='test',source='device:sonoff',option='forged',scene='scene')
        with self.assertRaises(ValueError):self.e.buttons.review(p,True)
        r=self.link()
        p=self.ctx(name='test',source=r['source'],option=r['option']['id'],scene='scene',id=r['id'])
        preview=self.e.buttons.review(p)
        with self.assertRaises(ValueError):self.e.buttons.review({**p,'confirm':False,'preview_hash':preview['preview_hash']},True)
        with self.assertRaises(ValueError):self.e.buttons.review({**p,'preview_hash':'old'},True)
        self.assertFalse(self.ha.writes())

    def test_rearm_invalidates_queued_old_events_and_prevents_cycles(self):
        r=self.link()
        p=self.ctx(name=r['name'],source=r['source'],option=r['option']['id'],scene=r['scene'],id=r['id'])
        proof=self.e.buttons.review(p)
        self.e.buttons.review({**p,'preview_hash':proof['preview_hash']},True)
        self.e.buttons.dispatch(self.layout['project'],r,self.event())
        self.assertFalse(self.ha.writes())
        raw=self.e.read();raw['projects'][self.layout['project']][0]['actions']=[{'device':'any','action':'press'}];self.e.write(raw)
        with self.assertRaises(ValueError):self.e.buttons.review(self.ctx(name='Cycle',source=r['source'],option=r['option']['id'],scene=r['scene']))

    def test_listener_and_snapshot_share_lock_order(self):
        layout_lock, engine_lock = threading.RLock(), threading.RLock()
        attempted = threading.Event()
        class LayoutLock:
            def __enter__(self):
                attempted.set(); layout_lock.acquire()
            def __exit__(self, *args): layout_lock.release()
        self.e.lock = engine_lock
        def provider():
            attempted.set()
            with layout_lock:
                self.e.stop_event.set()
                return copy.deepcopy(self.layout)
        self.e.layout_provider = provider
        with patch('nm_bridge.control_buttons.LAYOUT_LOCK', LayoutLock()):
            with layout_lock:
                self.e.buttons.start()
                self.assertTrue(attempted.wait(2))
                acquired = engine_lock.acquire(timeout=.5)
                if acquired: engine_lock.release()
            self.e.buttons.worker.join(2)
        self.assertFalse(self.e.buttons.worker.is_alive())
        self.assertTrue(acquired, 'Button listener acquired engine before layout')
