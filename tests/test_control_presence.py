import copy
import json
import tempfile
import unittest
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from nm_bridge.control_engine import ControlEngine, digest
from nm_bridge.control_presence import ControlPresence, in_window
from nm_bridge import climate_cards
from tests.test_control_engine import FakeHA, layout


class PresenceHA(FakeHA):
    def __init__(self):
        super().__init__()
        self.now = datetime(2026, 11, 16, 18, tzinfo=timezone.utc)
        self.states += [{'entity_id': 'alarm_control_panel.demo', 'state': 'disarmed', 'attributes': {}},
                        {'entity_id': 'input_boolean.nm_presence_sim_armed_away', 'state': 'off', 'attributes': {}}]
    def call(self, method, **args):
        result = super().call(method, **args)
        if method == 'call_service':
            state = next(s for s in self.states if s['entity_id'] == args['target']['entity_id'])
            state['state'] = 'on' if args['service'] == 'turn_on' else 'off'
            state['last_changed'] = self.now.isoformat()
        return result


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.layout, self.ha = layout(), PresenceHA()
        self.e = ControlEngine(self.tmp.name, lambda: copy.deepcopy(self.layout), lambda: self.ha)
        self.p = self.e.presence
    def context(self, **extra):
        return dict(confirm=True, project=self.layout['project'], fingerprint=digest(self.layout), revision=self.e.read()['revision'], **extra)
    def enable(self, **extra):
        payload = self.context(operation='preview', lights=['light.nm_lab_lamp'], start='18:00', end='23:00', mode='manual', alarm='', gap_min=1, gap_max=1, on_min=1, on_max=1)
        payload.update(extra)
        proof = self.p.handle(payload)
        self.assertEqual(self.ha.writes(), [])
        self.p.handle({**payload, 'operation':'apply', 'preview_hash':proof['preview_hash']})
    def tick(self, seconds=0):
        self.ha.now += timedelta(seconds=seconds); self.p.tick(self.ha.now)
    def state(self, entity):
        return next(s for s in self.ha.states if s['entity_id']==entity)
    def test_manual_pulse_and_stop_only_write_selected_light(self):
        self.enable(); self.tick()
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'on')
        self.tick(61); self.tick(1)
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
        self.assertFalse(self.p.runtime().get('owned'))
        self.assertEqual([x['service'] for x in self.ha.writes()],['turn_on','turn_off'])
    def test_alarm_away_gate_and_return_stop_never_commands_alarm(self):
        self.enable(mode='alarm',alarm='alarm_control_panel.demo'); self.tick(); self.assertEqual(self.ha.writes(),[])
        self.state('alarm_control_panel.demo')['state']='armed_home'; self.tick(1); self.assertEqual(self.ha.writes(),[])
        self.state('alarm_control_panel.demo')['state']='armed_away'; self.tick(1)
        self.state('alarm_control_panel.demo')['state']='disarmed'; self.tick(1); self.tick(1)
        self.assertEqual([x['domain'] for x in self.ha.writes()],['light','light'])
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
    def test_simulated_alarm_uses_same_gate(self):
        self.enable(mode='alarm',alarm='input_boolean.nm_presence_sim_armed_away'); self.tick()
        self.state('input_boolean.nm_presence_sim_armed_away')['state']='on'; self.tick(1)
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'on')
        self.state('input_boolean.nm_presence_sim_armed_away')['state']='unavailable'; self.tick(1)
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
    def test_already_on_light_untouched_and_manual_edit_not_reverted(self):
        self.state('light.nm_lab_lamp')['state']='on'; self.enable(); self.tick(); self.assertEqual(self.ha.writes(),[])
        self.state('light.nm_lab_lamp')['state']='off'; self.tick(61)
        self.state('light.nm_lab_lamp')['attributes']['brightness']=90
        self.tick(61)
        self.assertEqual([x['service'] for x in self.ha.writes()],['turn_on'])
    def test_restart_releases_owned_light_without_replaying_on(self):
        self.enable(); self.tick(); self.p=ControlPresence(self.e); self.tick(5); self.tick(1)
        self.assertEqual([x['service'] for x in self.ha.writes()],['turn_on','turn_off'])
    def test_offline_release_waits_then_recovers(self):
        self.enable(); self.tick(); original=copy.deepcopy(self.state('light.nm_lab_lamp'))
        self.state('light.nm_lab_lamp')['state']='unavailable'; self.tick(61); self.assertTrue(self.p.runtime().get('owned'))
        self.state('light.nm_lab_lamp').update(original); self.tick(1); self.tick(1)
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
    def test_conflicting_week_is_not_modified_and_suspends_simulation(self):
        row={'project':self.layout['project'],'entity':'light.nm_lab_lamp','commit':'input_text.commit'}
        climate_cards.write({'one':row},self.tmp.name)
        self.ha.states.append({'entity_id':'input_text.commit','state':json.dumps({'enabled':False}),'attributes':{}})
        self.enable(); self.state('input_text.commit')['state']=json.dumps({'enabled':True}); self.tick()
        self.assertEqual(self.ha.writes(),[])
        self.assertTrue(json.loads(self.state('input_text.commit')['state'])['enabled'])
    def test_wrong_project_or_unsupported_device_cannot_be_armed(self):
        for extra in ({'lights':['cover.nm_lab_shutter']},{'lights':['light.foreign']},{'project':'b'*64},{'mode':'alarm','alarm':'switch.boiler'}):
            with self.assertRaises(ValueError): self.enable(**extra)
        self.assertEqual(self.ha.writes(),[])
    def test_layout_change_releases_and_requires_new_review(self):
        self.enable(); self.tick(); self.layout['widgets'][0]['name']='Changed'; self.tick(1); self.tick(1)
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
        self.assertIn('Progetto modificato',self.p.runtime()['message'])
    def test_midnight_window_and_end_release(self):
        now=datetime(2026,11,16,23,tzinfo=timezone.utc)
        self.assertTrue(in_window(now,'Europe/Rome','20:00','01:00'))
        self.assertFalse(in_window(now+timedelta(hours=1),'Europe/Rome','20:00','01:00'))
        self.enable(); self.tick(); self.ha.now=datetime(2026,11,16,22,tzinfo=timezone.utc); self.tick()
        self.assertEqual(self.state('light.nm_lab_lamp')['state'],'off')
    def test_presence_and_snapshot_lock_order_cannot_deadlock(self):
        # Another request holds the layout lock before acquiring the engine,
        # exactly like ControlEngine.snapshot. Presence must use the same order.
        layout_lock, engine_lock = threading.RLock(), threading.RLock()
        attempted, finished = threading.Event(), threading.Event()
        class LayoutLock:
            def __enter__(self):
                attempted.set();layout_lock.acquire()
            def __exit__(self,*args):layout_lock.release()
        self.e.lock=engine_lock
        def provider():
            attempted.set()
            with layout_lock:return copy.deepcopy(self.layout)
        self.e.layout_provider=provider
        errors=[]
        def run():
            try:self.p.tick(self.ha.now)
            except Exception as exc:errors.append(exc)
            finally:finished.set()
        with patch('nm_bridge.control_presence.LAYOUT_LOCK',LayoutLock()):
            with layout_lock:
                thread=threading.Thread(target=run,daemon=True);thread.start()
                self.assertTrue(attempted.wait(2))
                acquired=engine_lock.acquire(timeout=.5)
                if acquired:engine_lock.release()
            self.assertTrue(finished.wait(2));thread.join()
        self.assertTrue(acquired,'Presence acquired engine before layout and blocked snapshot')
        self.assertEqual(errors,[])
