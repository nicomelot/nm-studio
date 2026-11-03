"""Persist installer reviews. No HA files, registry writes or KNX commands."""
import copy
import hashlib
import json
import os
import re
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

try:
    from .lab_devices import validate as validate_devices
except ImportError:
    from lab_devices import validate as validate_devices

KEY = re.compile(r"^[0-9a-f]{64}$")
MAX_SIZE = 8 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def evidence(data, ga):
    suggestions = [s for s in data.get('suggestions', []) if s.get('command') == ga]
    references = {ga}
    for suggestion in suggestions:
        references.update(v for v in suggestion.values() if isinstance(v, str) and re.fullmatch(r'\d+/\d+/\d+', v))
    return {'suggestions': suggestions, 'addresses': [a for a in data.get('addresses', []) if a.get('address') in references]}


class Sessions:
    def __init__(self, root):
        self.root = Path(root)
        self.pending = OrderedDict()
        self.lock = threading.RLock()

    def path(self, key):
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise ValueError("Identità progetto non valida")
        return self.root / (key + '.json')

    def read(self, key):
        path = self.path(key)
        if not path.exists():
            return None
        if path.stat().st_size > MAX_SIZE:
            raise ValueError("Progetto salvato oltre il limite")
        return json.loads(path.read_text(encoding='utf-8'))

    def list(self):
        with self.lock:
            items = []
            if self.root.exists():
                for path in sorted(self.root.glob('*.json')):
                    if KEY.fullmatch(path.stem):
                        record = self.read(path.stem)
                        items.append({'project': path.stem, 'label': record['label'],
                                      'revision': record['revision'], 'functions': len(record['reviews'])})
            return {'projects': items}

    def prepare(self, imported):
        with self.lock:
            data = copy.deepcopy(imported)
            key = data['project_key']
            old = self.read(key)
            originals = {d['command']: d for d in data.get('lab_candidates', [])}
            if len(originals) != len(data.get('lab_candidates', [])):
                raise ValueError('Funzioni duplicate da correggere')
            before = {d['command']: d for d in old['imported'].get('lab_candidates', [])} if old else {}
            reviews = old['reviews'] if old else {}
            changes = {'added': [], 'changed': [], 'removed': sorted(set(before) - set(originals)), 'retained': []}
            proposed = []
            for ga, item in originals.items():
                updated = copy.deepcopy(item)
                if ga in before:
                    # Any source change invalidates the selection, preserving only
                    # manual labels/rooms for review. Never infer bus approval.
                    changed = item != before[ga] or evidence(imported, ga) != evidence(old['imported'], ga)
                    changes['changed' if changed else 'retained'].append(ga)
                    if ga in reviews:
                        updated.update({k: reviews[ga][k] for k in ('name', 'room') if reviews[ga][k] != before[ga].get(k)})
                        updated['kind'] = item['kind'] if changed else reviews[ga]['kind']
                        updated['selected'] = False if changed else reviews[ga]['selected']
                else:
                    changes['added'].append(ga)
                    updated['selected'] = not bool(old) and len(proposed) < 200
                proposed.append(updated)
            token = digest(imported)
            if len(json.dumps(imported).encode()) > MAX_SIZE - 256000:
                raise ValueError('Progetto troppo grande per il salvataggio guidato')
            self.pending[token] = copy.deepcopy(imported)
            self.pending.move_to_end(token)
            while len(self.pending) > 4:
                self.pending.popitem(last=False)
            data.update(lab_candidates=proposed, session_token=token,
                        session_revision=old['revision'] if old else '',
                        session_label=old['label'] if old else '', session_changes=changes)
            return data

    def resume(self, key):
        with self.lock:
            saved = self.read(key)
            if not saved:
                raise ValueError('Progetto non salvato')
            return self.prepare(saved['imported'])

    def save(self, payload):
        with self.lock:
            if not isinstance(payload, dict) or payload.get('confirm') is not True:
                raise ValueError('Conferma del salvataggio obbligatoria')
            token = payload.get('token')
            if not isinstance(token, str) or not KEY.fullmatch(token):
                raise ValueError('Anteprima progetto non valida')
            imported = self.pending.get(token)
            if imported is None:
                raise ValueError('Anteprima scaduta: riprendi il progetto o reimporta ETS')
            key = imported['project_key']
            old = self.read(key)
            if payload.get('expected_revision', '') != (old['revision'] if old else ''):
                raise ValueError('Progetto aggiornato in un’altra finestra: riprendi prima di salvare')
            label = payload.get('label', '')
            if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80 or any(ord(c) < 32 for c in label):
                raise ValueError('Inserisci un nome progetto da 1 a 80 caratteri')
            candidates = {d['command']: d for d in imported.get('lab_candidates', [])}
            rows = payload.get('reviews')
            if not isinstance(rows, list) or len(rows) != len(candidates):
                raise ValueError('Revisione incompleta')
            clean, selected = {}, 0
            for row in rows:
                if not isinstance(row, dict) or row.get('command') not in candidates or row['command'] in clean or type(row.get('selected')) is not bool:
                    raise ValueError('Revisione duplicata o non valida')
                _, validated = validate_devices({'mode': 'virtual_devices', 'project': key, 'devices': [row]})
                clean[row['command']] = {**validated[0], 'selected': row['selected']}
                selected += row['selected']
            if selected > 200:
                raise ValueError('Seleziona al massimo 200 funzioni LAB')
            record = {'version': 1, 'label': label.strip(), 'imported': imported, 'reviews': clean}
            record['revision'] = digest(record)
            encoded = json.dumps(record, ensure_ascii=False, indent=2)
            if len(encoded.encode()) > MAX_SIZE:
                raise ValueError('Progetto oltre il limite di salvataggio')
            if not old and len(self.list()['projects']) >= 10:
                raise ValueError('Archivio pieno: massimo 10 progetti in questa versione')
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.path(key)
            if old:
                self._write(path.with_suffix('.bak'), json.dumps(old, ensure_ascii=False))
            self._write(path, encoded)
            return {'saved': True, 'project': key, 'revision': record['revision'], 'selected': selected,
                    'backup': bool(old), 'knx_traffic': False}

    @staticmethod
    def _write(path, content):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
                temporary = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
