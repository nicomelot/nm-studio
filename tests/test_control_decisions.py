import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from nm_bridge.control_engine import ControlEngine, binding, digest
from tests.test_control_engine import FakeHA, layout


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.layout, self.ha = layout(), FakeHA()
        for i, w in enumerate(self.layout['widgets']):
            w['entity_id'] = w['entity_id'].split('.')[0] + '.nm_lab_aaaaaaaaaaaa_' + str(i)
            self.ha.states[i]['entity_id'] = w['entity_id']
        now = datetime.now(timezone.utc)
        self.model = {'decision_id':'proposal-1', 'simulation':True, 'status':'ready',
                      'execution_enabled':False, 'generated_at':now.isoformat(),
                      'expires_at':(now+timedelta(minutes=10)).isoformat(),
                      'actions':[{'action':'Riduci consumi', 'reason':'Prova', 'explanation':'Solo simulazione',
                                  'proposal_only':True, 'requires_confirmation':True}]}
        self.ha.states.append({'entity_id':'sensor.decision', 'state':'ready', 'attributes':self.model})
        self.e = ControlEngine(self.tmp.name, lambda:copy.deepcopy(self.layout), lambda:self.ha)

    def payload(self, index=0, action='on', value=None):
        return {'confirm':True, 'project':self.layout['project'], 'fingerprint':digest(self.layout),
                'revision':0, 'decision_id':'proposal-1', 'proposal':0,
                'actions':[{'device':binding(self.layout['widgets'][index]),'action':action,'value':value}]}

    def test_preview_no_write_apply_once(self):
        p=self.payload();r=self.e.decisions.preview(p)
        self.assertFalse(self.ha.writes())
        p['token']=r['token'];self.assertEqual(self.e.decisions.apply(p)['status'],'accepted')
        with self.assertRaises(ValueError):self.e.decisions.apply(p)
        p['token']=self.e.decisions.preview(p)['token']
        self.assertTrue(self.e.decisions.apply(p)['duplicate'])
        self.assertEqual(len(self.ha.writes()),1)

    def test_stale_state_decision_confirmation_and_token(self):
        for change in ('state','model','expired','confirm','token','action'):
            with self.subTest(change=change):
                self.setUp();p=self.payload();p['token']=self.e.decisions.preview(p)['token']
                if change=='state':self.ha.states[0]['state']='on'
                if change=='model':self.model['actions'][0]['reason']='Changed'
                if change=='expired':self.model['expires_at']='2020-01-01T00:00:00+00:00'
                if change=='confirm':p['confirm']=False
                if change=='token':p['token']='forged'
                if change=='action':p['actions'][0]['action']='off'
                with self.assertRaises(ValueError):self.e.decisions.apply(p)
                self.assertFalse(self.ha.writes())

    def test_real_and_foreign_lab_rejected(self):
        for entity in ('light.real', 'light.nm_lab_otherproject_0'):
            self.layout['widgets'][0]['entity_id']=entity
            self.ha.states[0]['entity_id']=entity
            with self.assertRaises(ValueError):self.e.decisions.preview(self.payload())
        self.assertFalse(self.ha.writes())

    def test_cover_and_climate_supported(self):
        for i,a,v in ((1,'position',45),(2,'temperature',21)):
            self.model['decision_id']='proposal-'+str(i)
            p=self.payload(i,a,v);p['decision_id']=self.model['decision_id']
            p['token']=self.e.decisions.preview(p)['token']
            self.assertEqual(self.e.decisions.apply(p)['status'],'accepted')

    def test_timeout_and_project_change_rejected(self):
        p=self.payload();p['token']=self.e.decisions.preview(p)['token']
        self.e.decisions.previews[p['token']]['until']=0
        with self.assertRaises(ValueError):self.e.decisions.apply(p)
        p['token']=self.e.decisions.preview(p)['token']
        self.layout['widgets'][0]['fields']['command']='9/9/9'
        with self.assertRaises(ValueError):self.e.decisions.apply(p)
        self.assertFalse(self.ha.writes())
