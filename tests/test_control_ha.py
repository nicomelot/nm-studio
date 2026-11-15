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

    def test_imported_schedule_runs_and_revalidates_capabilities(self):
        from datetime import datetime, timezone
        key=self.add('media_player.wiim')
        now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
        from zoneinfo import ZoneInfo
        local=now.astimezone(ZoneInfo('Europe/Rome'))
        record={'id':'audio','name':'Audio mattino','kind':'schedule','room':'Test',
                'actions':[{'device':key,'action':'volume','value':25}],
                'triggers':[{'id':'morning','kind':'time','time':local.strftime('%H:%M'),'days':[local.weekday()],'value':35}]}
        self.e.save(self.ctx(record=record))
        self.assertFalse(self.ha.writes())
        preview=self.e.preview(self.ctx(id='audio'))
        self.assertEqual(preview['calls'][0]['service_data'],{'volume_level':.25})
        self.e.activate(self.ctx(id='audio',enabled=True,preview_hash=preview['preview_hash']))
        raw=self.e.read();raw['projects'][self.layout['project']][0]['activated_at']=now.isoformat();self.e.write(raw)
        self.e.tick(now);self.e.tick(now)
        self.assertEqual(len(self.ha.writes()),1)
        self.assertEqual(self.ha.writes()[0]['service_data'],{'volume_level':.35})
        self.ha.states[5]['attributes']['supported_features']=0
        with self.assertRaises(ValueError):self.e.preview(self.ctx(id='audio'))

    def test_mixed_scene_and_values(self):
        from nm_bridge.control_engine import clean_actions
        light=self.add('light.philips');audio=self.add('media_player.wiim')
        record={'id':'mixed','name':'Serata','kind':'scene','room':'Test','actions':[
            {'device':light,'action':'brightness','value':40},{'device':audio,'action':'source','value':'Line In'},
            {'device':audio,'action':'mute','value':False}]}
        self.e.save(self.ctx(record=record));p=self.e.preview(self.ctx(id='mixed'))
        result=self.e.run(self.ctx(id='mixed',preview_hash=p['preview_hash'],request_id='once'))
        self.assertEqual(result['sent'],3)
        self.assertEqual(self.ha.writes()[1]['service_data'],{'source':'Line In'})
        for action,value in [('volume',101),('mute','false'),('source','')]:
            with self.assertRaises(ValueError):clean_actions([{'device':audio,'action':action,'value':value}],self.e.combined(self.layout,self.e.read()))
