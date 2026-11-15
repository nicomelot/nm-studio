import copy
import tempfile
import unittest
from nm_bridge.control_engine import ControlEngine, binding, digest
from nm_bridge.control_ha import actions, plan
from tests.test_control_engine import FakeHA, layout


class HAWidgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.layout=layout();self.ha=FakeHA()
        self.ha.states.extend([
            {'entity_id':'light.philips','state':'off','attributes':{'supported_color_modes':['brightness']}},
            {'entity_id':'switch.sonoff','state':'off','attributes':{}},
            {'entity_id':'media_player.wiim','state':'paused','attributes':{'supported_features':16384+1+4+8+2048,'volume_level':.2,'source_list':['Wi-Fi','Line In']}},
            {'entity_id':'event.sonoff_button','state':'unknown','attributes':{'event_type':'single'}},
            {'entity_id':'button.sonoff','state':'unknown','attributes':{}},
        ])
        self.e=ControlEngine(self.tmp.name,lambda:copy.deepcopy(self.layout),lambda:self.ha)

    def ctx(self,**extra):
        return dict(confirm=True,project=self.layout['project'],fingerprint=digest(self.layout),revision=self.e.read()['revision'],**extra)

    def add(self,entity):
        self.e.features.add_widget(self.ctx(type='homeassistant',entity_id=entity,name='HA device',room='Test'))
        return binding(self.e.features.widgets(self.layout['project'])[-1])

    def test_import_is_read_only_and_prevents_duplicates(self):
        self.add('light.philips')
        with self.assertRaises(ValueError):self.add('light.philips')
        with self.assertRaises(ValueError):self.add('light.nm_lab_lamp')
        self.assertFalse(self.ha.writes())
        self.assertEqual(self.e.snapshot()['devices'][-1]['ha_actions'],['on','off','brightness'])

    def test_preview_confirm_and_single_send(self):
        key=self.add('switch.sonoff');p=self.ctx(device=key,action='on',value=None)
        p['token']=self.e.ha_widgets.preview(p)['token'];self.assertFalse(self.ha.writes())
        with self.assertRaises(ValueError):self.e.ha_widgets.apply({**p,'confirm':False})
        self.assertEqual(self.e.ha_widgets.apply(p)['status'],'accepted')
        with self.assertRaises(ValueError):self.e.ha_widgets.apply(p)
        self.assertEqual(len(self.ha.writes()),1)

    def test_media_capabilities_and_bounds(self):
        key=self.add('media_player.wiim')
        for action,value in [('volume',101),('volume',True),('source','Invented'),('off',None)]:
            with self.assertRaises(ValueError):self.e.ha_widgets.preview(self.ctx(device=key,action=action,value=value))
        p=self.ctx(device=key,action='volume',value=25);r=self.e.ha_widgets.preview(p)
        self.assertEqual(r['call']['service_data'],{'volume_level':.25})
        self.e.ha_widgets.apply({**p,'token':r['token']})
        self.assertEqual(self.ha.writes()[0]['domain'],'media_player')

    def test_changed_state_rejects_apply(self):
        key=self.add('light.philips');p=self.ctx(device=key,action='brightness',value=30)
        p['token']=self.e.ha_widgets.preview(p)['token']
        self.ha.states[3]['state']='on'
        with self.assertRaises(ValueError):self.e.ha_widgets.apply(p)
        self.assertFalse(self.ha.writes())

    def test_events_read_only_and_native_buttons(self):
        key=self.add('event.sonoff_button')
        with self.assertRaises(ValueError):self.e.ha_widgets.preview(self.ctx(device=key,action='press'))
        key=self.add('button.sonoff');p=self.ctx(device=key,action='press')
        p['token']=self.e.ha_widgets.preview(p)['token']
        self.e.ha_widgets.apply(p)
        self.assertEqual(self.ha.writes()[0]['service'],'press')
