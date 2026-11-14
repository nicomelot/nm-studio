import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from nm_bridge import control_engine as m

UTC = timezone.utc


def layout():
    return {'version': 1, 'project': 'a'*64, 'rooms': ['Casa / Sala'], 'structure': [], 'widgets': [
        {'name': 'Lampada', 'type': 'dimmer', 'room': 'Casa / Sala', 'entity_id': 'light.nm_lab_lamp', 'fields': {'command': '1/1/1', 'brightness': '1/1/2'}},
        {'name': 'Tapparella', 'type': 'cover', 'room': 'Casa / Sala', 'entity_id': 'cover.nm_lab_shutter', 'fields': {'command': '1/2/1', 'stop': '1/2/2'}},
        {'name': 'Termostato', 'type': 'climate', 'room': 'Casa / Sala', 'entity_id': 'climate.sala', 'fields': {'command': '2/1/1'}},
    ]}


class FakeHA:
    def __init__(self):
        self.calls = []
        self.fail_send = None
        self.config = {'time_zone': 'Europe/Rome', 'latitude': 45.46, 'longitude': 9.19, 'elevation': 120}
        self.states = [
            {'entity_id': 'light.nm_lab_lamp', 'state': 'off', 'attributes': {'supported_color_modes': ['brightness']}},
            {'entity_id': 'cover.nm_lab_shutter', 'state': 'open', 'attributes': {'supported_features': 15}},
            {'entity_id': 'climate.sala', 'state': 'heat', 'attributes': {'supported_features': 1, 'min_temp': 7, 'max_temp': 30, 'hvac_modes': ['heat', 'off']}},
        ]
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def call(self, method, **args):
        self.calls.append((method, args))
        if method == 'get_config': return copy.deepcopy(self.config)
        if method == 'get_states': return copy.deepcopy(self.states)
        if method == 'call_service':
            if self.fail_send is not None and len(self.writes()) == self.fail_send:
                raise ValueError('timeout')
            return {}
        raise AssertionError(method)
    def writes(self): return [a for method, a in self.calls if method == 'call_service']


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.layout = layout()
        self.ha = FakeHA()
        self.engine = m.ControlEngine(self.tmp.name, lambda: copy.deepcopy(self.layout), lambda: self.ha)
    def context(self, **extra):
        return dict(confirm=True, project=self.layout['project'], fingerprint=m.digest(self.layout), revision=self.engine.read()['revision'], **extra)
    def action(self, index=0, action='on', value=None):
        return {'device': m.binding(self.layout['widgets'][index]), 'action': action, 'value': value}
    def scene(self, kind='scene', actions=None, triggers=None):
        return {'id': 'demo', 'name': 'Test', 'kind': kind, 'room': 'Casa / Sala',
                'actions': actions or [self.action()], 'triggers': triggers or [{'id': 'morning', 'kind': 'time', 'time': '07:00', 'days': list(range(7))}]}
    def save(self, **kwargs):
        return self.engine.save(self.context(record=self.scene(**kwargs)))
    def enable(self):
        check = self.engine.preview(self.context(id='demo'))
        return self.engine.activate(self.context(id='demo', enabled=True, preview_hash=check['preview_hash']))

    def test_lab_import_preserves_originals_and_never_commands(self):
        ident = 'light.nm_lab_aaaaaaaaaaaa_1_1_1'
        self.ha.states.append({'entity_id': ident, 'state': 'off', 'attributes': {'supported_color_modes': ['brightness']}})
        with patch.object(m, 'save_layout', side_effect=lambda p:p) as save:
            result = self.engine.add_lab(self.context(entities=[{'entity_id':ident,'name':'Prova'}]))
            self.assertEqual(result['widgets'][:3], self.layout['widgets'])
            self.assertEqual(result['widgets'][3]['type'], 'dimmer')
            self.assertEqual(result['widgets'][3]['room'], 'Collaudo simulato')
            self.assertEqual(self.ha.writes(), [])
            for entities in ([{'entity_id':'climate.sala','name':'Real'}], [{'entity_id':ident,'name':'X'}]*2):
                with self.assertRaises(ValueError): self.engine.add_lab(self.context(entities=entities))
            self.ha.states[-1]['state'] = 'unavailable'
            with self.assertRaises(ValueError): self.engine.add_lab(self.context(entities=[{'entity_id':ident,'name':'X'}]))
            self.assertEqual(save.call_count, 1)

    def test_save_preview_and_snapshot_never_send_commands(self):
        self.save()
        snap = self.engine.snapshot()
        self.assertEqual(len(snap['devices']), 3)
        self.engine.preview(self.context(id='demo'))
        self.assertEqual(self.ha.writes(), [])

    def test_scene_is_durable_and_manual_retries_are_idempotent(self):
        self.save(actions=[self.action(0,'brightness',45), self.action(1,'close')])
        proof = self.engine.preview(self.context(id='demo'))
        payload = self.context(id='demo', preview_hash=proof['preview_hash'], request_id='req1')
        result = self.engine.run(payload)
        self.assertEqual(result['status'], 'accepted')
        self.assertEqual(len(self.ha.writes()), 2)
        other = m.ControlEngine(self.tmp.name, lambda: self.layout, lambda: self.ha)
        self.assertTrue(other.run(payload)['duplicate'])
        self.assertEqual(len(self.ha.writes()), 2)
        self.assertEqual(self.ha.writes()[0]['service_data'], {'brightness_pct': 45})

    def test_stale_binding_project_revision_and_no_consent_rejected(self):
        p = self.context(record=self.scene())
        for change in ({'confirm':False},{'project':'b'*64},{'fingerprint':'bad'},{'revision':99}):
            with self.assertRaises(ValueError): self.engine.save({**p,**change})
        self.layout['widgets'][0]['entity_id'] = 'light.other'
        with self.assertRaises(ValueError): self.engine.save(self.context(record=p['record']))
        self.assertEqual(self.ha.writes(), [])

    def test_all_actions_checked_before_first_write(self):
        self.save(actions=[self.action(), self.action(1,'position',50)])
        proof = self.engine.preview(self.context(id='demo'))
        self.ha.states[1]['state'] = 'unavailable'
        result = self.engine.run(self.context(id='demo',preview_hash=proof['preview_hash'],request_id='req2'))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.ha.writes(), [])

    def test_mid_scene_failure_records_partial_result_without_retry(self):
        self.save(actions=[self.action(),self.action(1,'close')])
        proof = self.engine.preview(self.context(id='demo'))
        self.ha.fail_send = 2
        p = self.context(id='demo',preview_hash=proof['preview_hash'],request_id='partial')
        result = self.engine.run(p)
        self.assertEqual(result['sent'],1)
        self.assertEqual(result['status'],'error')
        self.assertTrue(self.engine.run(p)['duplicate'])
        self.assertEqual(len(self.ha.writes()),2)

    def test_climate_range_mode_and_cover_feature_checks(self):
        for a in (self.action(2,'temperature',31), self.action(2,'hvac_mode','cool')):
            with self.assertRaises(ValueError):m.service_plan(self.layout,[a],self.ha)
        call=m.service_plan(self.layout,[self.action(2,'temperature',20.5)],self.ha)[0]
        self.assertEqual(call['service'],'set_temperature')
        self.assertEqual(call['target'],{'entity_id':'climate.sala'})
        self.ha.states[1]['attributes']['supported_features']=3
        with self.assertRaises(ValueError):m.service_plan(self.layout,[self.action(1,'position',20)],self.ha)

    def test_schedule_is_paused_after_save_and_edit(self):
        self.save(kind='schedule')
        self.assertFalse(self.engine.read()['projects']['a'*64][0]['enabled'])
        self.enable()
        self.assertTrue(self.engine.read()['projects']['a'*64][0]['enabled'])
        self.save(kind='schedule')
        self.assertFalse(self.engine.read()['projects']['a'*64][0]['enabled'])
        self.assertEqual(self.ha.writes(),[])

    def test_weekly_setpoints_and_once_only_across_restart(self):
        self.save(kind='schedule',actions=[self.action(2,'temperature',20)],triggers=[{'id':'wake','kind':'time','time':'07:00','days':[0,1,2,3,4],'value':21.5}])
        self.enable()
        raw=self.engine.read();raw['projects']['a'*64][0]['activated_at']='2026-01-01T00:00:00+00:00';self.engine.write(raw)
        due=datetime(2026,11,16,6,0,15,tzinfo=UTC)
        self.engine.tick(due)
        other=m.ControlEngine(self.tmp.name,lambda:self.layout,lambda:self.ha)
        other.tick(due+timedelta(seconds=10))
        self.assertEqual(len(self.ha.writes()),1)
        self.assertEqual(self.ha.writes()[0]['service_data'],{'temperature':21.5})
        other.tick(datetime(2026,11,17,6,5,tzinfo=UTC))
        self.assertEqual(len(self.ha.writes()),1)

    def test_activation_does_not_catch_up_earlier_occurrence(self):
        self.save(kind='schedule');self.enable()
        raw=self.engine.read();raw['projects']['a'*64][0]['activated_at']='2026-11-16T06:00:20+00:00';self.engine.write(raw)
        self.engine.tick(datetime(2026,11,16,6,0,30,tzinfo=UTC))
        self.assertEqual(self.ha.writes(),[])

    def test_different_project_and_changed_device_cannot_send_old_schedule(self):
        self.save(kind='schedule');self.enable()
        raw=self.engine.read();raw['projects']['a'*64][0]['activated_at']='2026-01-01T00:00:00+00:00';self.engine.write(raw)
        due=datetime(2026,11,16,6,0,15,tzinfo=UTC)
        self.layout['project']='b'*64;self.engine.tick(due)
        self.assertEqual(self.ha.writes(),[])
        self.layout['project']='a'*64;self.layout['widgets'][0]['fields']['command']='3/1/1';self.engine.tick(due)
        self.assertEqual(self.ha.writes(),[])
        self.assertEqual(self.engine.history('a'*64)[0]['status'],'error')

    def test_solar_offset_day_selection_and_polar_absence(self):
        t=[{'id':'sun','kind':'sunset','offset':30,'days':[0]}]
        now=datetime(2026,11,16,tzinfo=UTC)
        runs=m.occurrences(t,self.ha.config,now,horizon=2)
        self.assertEqual(len(runs),1)
        zero=m.occurrences([{**t[0],'offset':0}],self.ha.config,now,horizon=2)[0][0]
        self.assertEqual(runs[0][0]-zero,timedelta(minutes=30))
        polar={**self.ha.config,'latitude':89.0}
        self.assertEqual(m.occurrences(t,polar,now,horizon=2),[])

    def test_dst_gap_skipped_and_fold_uses_first_instant(self):
        triggers=[{'id':'night','kind':'time','time':'02:30','days':[6]}]
        spring=m.occurrences(triggers,self.ha.config,datetime(2026,3,29,tzinfo=UTC),horizon=1)
        self.assertEqual(spring,[])
        fall=m.occurrences(triggers,self.ha.config,datetime(2026,10,25,tzinfo=UTC),horizon=1)
        self.assertEqual(len(fall),1)
        self.assertEqual(fall[0][0],datetime(2026,10,25,0,30,tzinfo=UTC))

    def test_trigger_and_action_validation(self):
        for t in ({'id':'x','kind':'time','time':'25:00','days':[0]}, {'id':'x','kind':'time','time':'07:00','days':[]}, {'id':'x','kind':'sunset','offset':181,'days':[0]}):
            with self.assertRaises(ValueError):m.clean_triggers([t])
        for value in (True,float('nan'),float('inf'),-1,101):
            with self.assertRaises(ValueError):m.clean_actions([self.action(0,'brightness',value)],self.layout)

    def test_reordering_and_rename_preserve_binding_wiring_change_does_not(self):
        before=m.binding(self.layout['widgets'][0])
        self.layout['widgets'][0].update(name='Altro nome',room='Altra stanza')
        self.assertEqual(before,m.binding(self.layout['widgets'][0]))
        self.layout['widgets'][0]['fields']['command']='1/1/9'
        self.assertNotEqual(before,m.binding(self.layout['widgets'][0]))

    def test_real_knx_alignment_gate_is_not_bypassed(self):
        self.layout['widgets'][0]['entity_id']='light.real'
        self.ha.states[0]['entity_id']='light.real'
        with patch.object(m,'compare',return_value={'status':'review'}):
            with self.assertRaises(ValueError):m.service_plan(self.layout,[self.action()],self.ha)
        self.assertEqual(self.ha.writes(),[])

    def test_direct_command_preview_and_retry(self):
        actions = [self.action(1, 'close')]
        preview = self.engine.action_preview(self.context(actions=actions))
        self.assertEqual(self.ha.writes(), [])
        payload = self.context(actions=actions, preview_hash=preview['preview_hash'], request_id='direct')
        self.assertEqual(self.engine.action_run(payload)['status'], 'accepted')
        self.assertTrue(self.engine.action_run(payload)['duplicate'])
        self.assertEqual(len(self.ha.writes()), 1)
        with self.assertRaises(ValueError):
            self.engine.action_run({**payload, 'actions': [self.action(1, 'open')]})

    def test_assign_keeps_wiring_and_unselected_widgets(self):
        original = copy.deepcopy(self.layout)
        with patch.object(m, 'save_layout', side_effect=lambda p:p) as save:
            result = self.engine.assign(self.context(room='Casa / Studio', devices=[m.binding(original['widgets'][0])]))
        self.assertEqual(result['widgets'][0]['room'], 'Casa / Studio')
        self.assertEqual(result['widgets'][0]['fields'], original['widgets'][0]['fields'])
        self.assertEqual(result['widgets'][1:], original['widgets'][1:])
        self.assertEqual(result['structure'], original['structure'])
        save.assert_called_once()

    def test_schedule_conflict_with_active_program(self):
        self.save(kind='schedule'); self.enable()
        other = self.scene(kind='schedule', actions=[self.action(0, 'off')])
        other['id'] = 'other'
        self.engine.save(self.context(record=other))
        with self.assertRaisesRegex(ValueError, 'Conflitto'):
            self.engine.preview(self.context(id='other'))
        self.assertEqual(self.ha.writes(), [])

    def test_duplicate_slots_and_off_only_are_rejected(self):
        trigger = {'id':'a', 'kind':'time', 'time':'07:00', 'days':[0]}
        with self.assertRaises(ValueError):
            m.clean_triggers([trigger, {**trigger, 'id':'b'}])
        self.layout['widgets'][0]['command_mode'] = 'off_only'
        with self.assertRaises(ValueError):
            m.clean_actions([self.action()], self.layout)
        self.assertEqual(m.clean_actions([self.action(0,'off')],self.layout)[0]['action'],'off')

    def test_http_endpoints_are_ingress_only_and_require_confirmation(self):
        from test_lab_http import request, bridge
        for path in ('/control/save','/control/run','/control/activate','/control/action-run','/control/assign'):
            self.assertEqual(request(path,{},address='192.168.1.8')['status'],403)
            with patch.object(bridge,'CONTROL',self.engine):
                self.assertEqual(request(path,{})['status'],400)


if __name__=='__main__':unittest.main()
