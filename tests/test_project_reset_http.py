"""Real ingress dispatch, isolated filesystem and simulated HA; no network."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nm_bridge'))
import bridge
from test_project_reset import fixture, PROJECT


class ResetHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.reset, self.ha = fixture(self.tmp.name)
        original = self.ha.call
        self.ha.call = lambda method, **args: [{'id':'owner','is_owner':True,'is_active':True}, {'id':'guest','is_active':True}] if method=='config/auth/list' else original(method, **args)
        self.patches = [patch.object(bridge, 'CONTROL', self.reset.e), patch.object(bridge, 'RESET', self.reset)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
    def request(self, path, payload=None, user='owner', address=None):
        h = object.__new__(bridge.Handler); h.path = path
        h.client_address = (address or bridge.INGRESS_PROXY, 1)
        raw = json.dumps(payload).encode(); h.rfile = io.BytesIO(raw)
        h.headers = {'Content-Type':'application/json','Content-Length':str(len(raw)), 'X-Remote-User-Id':user, 'Sec-Fetch-Site':'same-origin'}
        result = {}
        h.respond = lambda status, content_type, body: result.update(status=status, type=content_type, body=body)
        h.send_error = lambda status: result.update(status=status)
        (h.do_GET if payload is None else h.do_POST)()
        if result.get('type','').startswith('application/json'): result['data'] = json.loads(result['body'])
        return result
    def test_admin_only_real_routes_preview_backup_download_confirm_and_empty_project(self):
        path='/control/reset'; args={'operation':'preview','project':PROJECT}
        self.assertEqual(self.request(path,args,address='127.0.0.1')['status'],403)
        self.assertEqual(self.request(path,args,user='guest')['status'],400)
        self.assertEqual(self.request(path,args,user='')['status'],400)
        review=self.request(path,args)['data']
        backup=self.request(path,{**args,'operation':'backup','fingerprint':review['fingerprint']})['data']
        download='/control/reset-backup?id='+backup['backup_id']
        self.assertEqual(self.request(download,user='guest')['status'],404)
        zip_response=self.request(download)
        self.assertEqual(zip_response['status'],200);self.assertTrue(zip_response['body'].startswith(b'PK'))
        request={**args,'operation':'apply','fingerprint':review['fingerprint'],'backup_id':backup['backup_id'],'confirm':True,'phrase':review['phrase'],'backup_downloaded':True}
        result=self.request(path,request)
        self.assertEqual(result['status'],200);self.assertTrue(result['data']['complete'])
        self.assertEqual(self.reset.e.layout_provider()['project'],'')
        self.assertTrue(self.reset.backup_path(backup['backup_id']).exists())
        self.assertFalse(any(m=='call_service' for m,_ in self.ha.calls))
