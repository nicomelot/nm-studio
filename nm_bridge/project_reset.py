"""Reviewed, backed-up removal of one NM project. Never executes device services.

Only exact project metadata/helper identities are automatic ownership evidence.
Legacy standalone NM dashboards require explicit selection. Unknown HA entities,
areas, integrations, YAML and shared frontend resources are never guessed away.
"""
import base64
import copy
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path

try:
    from .widget_layout import LAYOUT_LOCK
    from .climate_cards import LOCK as CARD_LOCK, key
    from .lab_virtual import WRITE_LOCK, _owned_package
except ImportError:
    from widget_layout import LAYOUT_LOCK
    from climate_cards import LOCK as CARD_LOCK, key
    from lab_virtual import WRITE_LOCK, _owned_package

MAX_BYTES = 80 * 1024 * 1024
JOURNAL = 'nm_reset_pending.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def atomic(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def clean_cards(value, project):
    """Remove only explicitly project-bound NM cards from shared dashboards."""
    if isinstance(value, list):
        return [clean_cards(v, project) for v in value if not (
            isinstance(v, dict) and (v.get('project') == project
            and v.get('type', '').startswith('custom:nm-') or
            str(v.get('path', '')).startswith('nm-' + project[:12] + '-') or
            v.get('path') == 'nm-dispositivi-' + project[:12]))]
    if isinstance(value, dict):
        return {k: clean_cards(v, project) for k, v in value.items()}
    return value


class ProjectReset:
    def __init__(self, engine, sessions=None, config_root='/homeassistant', paths=None):
        self.e = engine
        self.root = Path(engine.root)
        self.config_root = Path(config_root)
        self.sessions = sessions
        self.paths = paths or {
            'widgets': self.root / 'nm_knx_widget_layout.json',
            'layout': self.root / 'nm_control_layout.json',
            'approved': self.root / 'nm_knx_approved.json',
            'notes': self.root / 'nm_ets_review.json',
            'links': self.root / 'nm_link_drafts.json',
            'floorplans': self.root / 'nm_floorplans.json',
            'modules': self.root / 'nm_module_plan.json',
        }

    def checked(self, path, root=None):
        root = Path(root or self.root).absolute()
        path = Path(path).absolute()
        if not path.is_relative_to(root):
            raise ValueError('Percorso fuori dall’archivio NM')
        for part in [path, *path.parents]:
            if part.is_symlink():
                raise ValueError('Collegamento simbolico non ammesso nel reset')
            if part == root:
                break
        return path

    def read_json(self, path, default=None):
        self.checked(path)
        if not path.exists():
            return copy.deepcopy(default)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('Archivio troppo grande per un backup sicuro')
        return json.loads(path.read_text(encoding='utf-8'))

    def pending(self):
        return self.read_json(self.root / JOURNAL)

    def inventory(self, payload, ws):
        layout = self.e.layout_provider()
        project = payload.get('project')
        if not isinstance(project, str) or not re.fullmatch('[a-f0-9]{64}', project) or layout.get('project') != project:
            raise ValueError('Seleziona il progetto attivo e ripeti l’anteprima')
        selected = payload.get('legacy_dashboards', [])
        if not isinstance(selected, list) or any(not isinstance(p, str) for p in selected):
            raise ValueError('Selezione pagine non valida')
        raw = self.e.read()
        cards = self.read_json(self.root / 'nm_climate_cards.json', {})
        projects = {p for p in raw.get('projects', {}) if p != project}
        projects |= {r.get('project') for r in cards.values() if r.get('project') != project}
        folder = self.checked(self.root / 'nm_projects')
        if folder.exists():
            projects |= {p.stem for p in folder.glob('*.json') if re.fullmatch('[a-f0-9]{64}', p.stem) and p.stem != project}
        projects.discard(None)
        changes, blockers, preserved = [], [], []

        def change(path, after=None, root='data'):
            parent = self.root if root == 'data' else self.config_root
            path = self.checked(path, parent)
            if not path.exists():
                return
            before = path.read_bytes()
            if len(before) > MAX_BYTES:
                raise ValueError('File troppo grande: ' + path.name)
            encoded = None if after is None else base64.b64encode(json.dumps(after, ensure_ascii=False).encode()).decode()
            if encoded == base64.b64encode(before).decode():
                return
            changes.append({'root': root, 'path': path.relative_to(parent).as_posix(),
                            'before': base64.b64encode(before).decode(), 'after': encoded})

        change(self.paths['widgets'])
        change(folder / (project + '.json'))
        change(self.root / ('diagrams_' + project + '.json'))
        updated = copy.deepcopy(raw)
        for value in updated.values():
            if isinstance(value, dict):
                value.pop(project, None)
        updated['revision'] = updated.get('revision', 0) + 1
        change(self.e.path, updated)
        change(self.root / 'nm_climate_cards.json', {k: v for k, v in cards.items() if v.get('project') != project})
        for path in [self.paths['notes'], self.root / 'native_area_mapping.json']:
            value = self.read_json(path, {})
            if project in value:
                value.pop(project)
                change(path, value)
        runtime = self.read_json(self.root / 'nm_presence_runtime.json', {})
        if runtime.get('project') == project:
            if runtime.get('owned'):
                blockers.append('Ferma prima la presenza simulata e attendi il rilascio della luce in uso.')
            change(self.root / 'nm_presence_runtime.json')
        if self.e.journal.exists():
            with self.e.db() as db:
                if db.execute("SELECT 1 FROM holds WHERE project=? AND status!='closed' LIMIT 1", (project,)).fetchone():
                    blockers.append('Rilascia i pulsanti momentanei e attendi la conferma del valore 0.')
        # Older files have no project ID: only clear them in a single-project installation.
        for label in ('layout', 'approved', 'links', 'floorplans', 'modules'):
            if self.paths[label].exists():
                if projects:
                    blockers.append('Archivio legacy condiviso con altri progetti: ' + self.paths[label].name)
                else:
                    change(self.paths[label])
        package = self.checked(self.config_root / 'packages/nm_lab_virtual.yaml', self.config_root)
        if package.exists():
            content = package.read_bytes()
            prefixes = set(re.findall(rb'nm_lab_([a-f0-9]{12})_', content))
            if _owned_package(content) and prefixes == {project[:12].encode()}:
                change(package, root='ha')
            else:
                preserved.append('Package simulati condiviso o senza identità certa: conservato.')

        states = {s['entity_id']: s for s in ws.call('get_states')}
        owned = set()
        config_values = set()
        for ident, row in cards.items():
            if row.get('project') != project:
                continue
            canonical = key(project, row['entity'])
            if ident != canonical:
                blockers.append('Identità aiutanti incoerente: ' + ident)
                continue
            owned.update(s for s in strings(row) if re.fullmatch(r'input_(?:text|number|boolean)\.[a-z0-9_]+', s) and ident in s)
            config_values.update(strings(row.get('days', [])))
            config_values.add(row.get('commit'))
            config_values.update(strings(row.get('calendar', {}).get('profiles', {})))
            owned.update(('input_boolean.nm_favorite_' + ident, 'input_number.nm_favorite_order_' + ident))
        helpers = []
        for domain in ('input_boolean', 'input_number', 'input_text'):
            for item in ws.call(domain + '/list'):
                entity = domain + '.' + item['id']
                if entity in owned:
                    helpers.append({'entity': entity, 'config': item, 'state': states.get(entity, {}).get('state')})
        dashboards, candidates = [], []
        listed = ws.call('lovelace/dashboards/list')
        default_config = None
        try:
            default_config = ws.call('lovelace/config')
            listed = listed + [{'url_path': 'lovelace', 'title': 'Panoramica classica', 'mode': 'storage'}]
        except Exception as exc:
            if getattr(exc, 'code', None) != 'config_not_found':
                blockers.append('Panoramica classica non verificabile: ' + str(exc)[:120])
        for row in listed:
            path = row['url_path']
            if row.get('mode', 'storage') != 'storage':
                preserved.append('Dashboard YAML conservata: ' + path)
                continue
            current = default_config if path == 'lovelace' else ws.call('lovelace/config', url_path=path)
            values = set(strings(current))
            bound_projects = {v for v in values if re.fullmatch('[a-f0-9]{64}', v)}
            foreign = bool(bound_projects - {project})
            automatic = path.startswith('nm-studio-') and project[:12] in path and not foreign
            legacy = path.startswith('nm-studio-') and not foreign and any(v.startswith('custom:nm-') for v in values)
            if legacy and not automatic:
                candidates.append({'path': path, 'title': row.get('title', path)})
            remove = automatic or legacy and path in selected
            after = None if remove else clean_cards(current, project)
            if remove or after != current:
                dashboards.append({'metadata': row, 'before': current, 'after': after})
        if set(selected) - {c['path'] for c in candidates}:
            raise ValueError('Pagina non attribuibile a NM: selezione rifiutata')
        for d in dashboards:
            path = d['metadata']['url_path']
            if re.fullmatch('[a-z0-9-]+', path):
                for directory in ('dashboard_backups', 'nm_overview_backups'):
                    change(self.root / directory / 'baselines' / (path + '.json'))
        preserved += ['Integrazioni, dispositivi fisici e stanze Home Assistant conservati.',
                      'Entità KNX preesistenti senza registro di creazione NM: verifica manuale nel pannello KNX.',
                      'Risorse grafiche condivise e backup precedenti conservati.']
        # No volatile sensor state in the reviewed fingerprint. Weekly content is configuration.
        plan = {'project': project, 'files': changes, 'helpers': sorted(helpers, key=lambda h: h['entity']),
                'dashboards': sorted(dashboards, key=lambda d: d['metadata']['url_path']),
                'candidates': candidates, 'preserved': preserved, 'blockers': blockers,
                'legacy_dashboards': sorted(selected), 'restart_required': any(f['root'] == 'ha' for f in changes)}
        proof = copy.deepcopy(plan)
        for h in proof['helpers']:
            if h['entity'] not in config_values and not h['entity'].startswith(('input_boolean.nm_favorite_', 'input_number.nm_favorite_order_')):
                h.pop('state', None)
        plan['fingerprint'] = digest(proof)
        return plan

    def summary(self, plan):
        return {'project': plan['project'], 'fingerprint': plan['fingerprint'],
                'phrase': 'AZZERA ' + plan['project'][:12], 'blockers': plan['blockers'],
                'files': [f['path'] for f in plan['files']],
                'helpers': [h['entity'] for h in plan['helpers']],
                'dashboards': [{'path': d['metadata']['url_path'], 'title': d['metadata'].get('title'),
                                'action': 'Elimina pagina' if d['after'] is None else 'Rimuove solo le card NM del progetto'} for d in plan['dashboards']],
                'candidates': plan['candidates'], 'preserved': plan['preserved'],
                'restart_required': plan['restart_required'], 'legacy_dashboards': plan['legacy_dashboards']}

    def backup_path(self, ident):
        if not isinstance(ident, str) or not re.fullmatch('[a-f0-9]{32}', ident):
            raise ValueError('Backup non valido')
        return self.checked(self.root / 'nm_reset_backups' / (ident + '.zip'))

    def backup(self, plan):
        ident = uuid.uuid4().hex
        path = self.backup_path(ident)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(plan, ensure_ascii=False).encode()
        if len(data) > MAX_BYTES:
            raise ValueError('Backup oltre il limite: nessuna cancellazione')
        with path.open('xb') as file:
            with zipfile.ZipFile(file, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', data)
                archive.writestr('RIPRISTINO.txt', 'Backup NM prima dell’azzeramento. manifest.json contiene configurazioni e valori degli aiutanti HA, dashboard complete e file originali in base64. Ripristino assistito: ricreare gli aiutanti tramite HA, ripristinare le dashboard e i file indicati. Non è un backup completo di Home Assistant. I file e le dashboard possono contenere personalizzazioni: conservare il file in un luogo riservato.\n')
                if self.e.journal.exists():
                    temp = path.with_suffix('.sqlite')
                    try:
                        with self.e.db() as source, sqlite3.connect(temp) as dest:
                            source.backup(dest)
                        archive.write(temp, 'nm_control_runs.sqlite')
                    finally:
                        temp.unlink(missing_ok=True)
            file.flush()
            os.fsync(file.fileno())
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() or archive.read('manifest.json') != data:
                raise ValueError('Backup non verificato: reset annullato')
        return {'backup_id': ident, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'download': 'control/reset-backup?id=' + ident, **self.summary(plan)}

    def load_backup(self, ident):
        with zipfile.ZipFile(self.backup_path(ident)) as archive:
            if archive.getinfo('manifest.json').file_size > MAX_BYTES or archive.testzip():
                raise ValueError('Backup non integro')
            return json.loads(archive.read('manifest.json'))

    def handle(self, payload):
        # Order matches the scheduler and card provisioning. Only one reset at a time.
        with LAYOUT_LOCK, self.e.lock, CARD_LOCK, WRITE_LOCK:
            operation = payload.get('operation', 'preview')
            pending = self.pending()
            if operation == 'status':
                return {'pending': pending}
            if pending and operation != 'resume':
                raise ValueError('Azzeramento interrotto: riprendi dal backup ' + pending['backup_id'])
            with self.e.connection_factory() as ws:
                if operation == 'resume':
                    if not pending or payload.get('backup_id') != pending['backup_id']:
                        raise ValueError('Nessun azzeramento da riprendere')
                    plan = self.load_backup(pending['backup_id'])
                else:
                    plan = self.inventory(payload, ws)
                if operation == 'preview':
                    return self.summary(plan)
                if plan['blockers']:
                    raise ValueError(' · '.join(plan['blockers']))
                if operation in ('backup', 'apply') and payload.get('fingerprint') != plan['fingerprint']:
                    raise ValueError('Dati cambiati: ripeti anteprima e backup')
                if operation == 'backup':
                    return self.backup(plan)
                if operation not in ('apply', 'resume'):
                    raise ValueError('Operazione reset non valida')
                if payload.get('confirm') is not True or payload.get('phrase') != 'AZZERA ' + plan['project'][:12] or payload.get('backup_downloaded') is not True:
                    raise ValueError('Scarica il backup e digita la conferma esatta')
                ident = payload.get('backup_id')
                saved = self.load_backup(ident)
                if saved['fingerprint'] != plan['fingerprint']:
                    raise ValueError('Backup non corrispondente all’anteprima')
                if not pending:
                    pending = {'backup_id': ident, 'project': plan['project'], 'done': [], 'started': time.time()}
                    atomic(self.root / JOURNAL, pending)
                try:
                    self.apply_plan(ws, saved, pending)
                except Exception as exc:
                    pending['error'] = str(exc)[:250]
                    atomic(self.root / JOURNAL, pending)
                    return {'complete': False, 'pending': pending, 'backup_id': ident,
                            'message': 'Azzeramento incompleto. Programmi NM sospesi; backup conservato. Riprendi per completare.'}
                (self.root / JOURNAL).unlink()
                if self.sessions:
                    with self.sessions.lock:
                        self.sessions.pending.clear()
                self.e.decisions.previews.clear()
                self.e.ha_widgets.previews.clear()
                return {'complete': True, 'backup_id': ident, 'restart_required': saved['restart_required'],
                        'preserved': saved['preserved'], 'message': 'Progetto NM azzerato. Puoi importare un nuovo file ETS.'}

    def apply_plan(self, ws, plan, pending):
        def step(name, action):
            # Reconcile even completed steps: HA may have changed during an interruption.
            action()
            if name not in pending['done']:
                pending['done'].append(name)
            atomic(self.root / JOURNAL, pending)
        # Each action reconciles an ambiguous transport failure before retrying.
        for d in plan['dashboards']:
            path = d['metadata']['url_path']
            def dashboard(d=d, path=path):
                listed = ws.call('lovelace/dashboards/list')
                entry = next((r for r in listed if r['url_path'] == path), None)
                if entry is None and d['after'] is None:
                    return
                args = {} if path == 'lovelace' else {'url_path': path}
                current = ws.call('lovelace/config', **args)
                if current == d['after']:
                    return
                if current != d['before']:
                    raise ValueError('Pagina modificata durante il reset: ' + path)
                if d['after'] is None:
                    ws.call('lovelace/dashboards/delete', dashboard_id=entry['id'])
                    if any(r['url_path'] == path for r in ws.call('lovelace/dashboards/list')):
                        raise ValueError('Rimozione pagina non confermata: ' + path)
                else:
                    ws.call('lovelace/config/save', config=d['after'], **args)
                    if ws.call('lovelace/config', **args) != d['after']:
                        raise ValueError('Modifica pagina non verificata: ' + path)
            step('dashboard:' + path, dashboard)
        for h in plan['helpers']:
            domain, ident = h['entity'].split('.', 1)
            def helper(domain=domain, ident=ident, h=h):
                current = next((v for v in ws.call(domain + '/list') if v['id'] == ident), None)
                if current is None:
                    return
                if current != h['config']:
                    raise ValueError('Aiutante modificato: ' + h['entity'])
                ws.call(domain + '/delete', **{domain + '_id': ident})
                if any(v['id'] == ident for v in ws.call(domain + '/list')):
                    raise ValueError('Aiutante non rimosso: ' + h['entity'])
            step('helper:' + h['entity'], helper)
        for f in plan['files']:
            def local(f=f):
                root = self.root if f['root'] == 'data' else self.config_root
                path = self.checked(root / f['path'], root)
                before = base64.b64decode(f['before'])
                after = base64.b64decode(f['after']) if f['after'] is not None else None
                current = path.read_bytes() if path.exists() else None
                if current == after:
                    return
                if current != before:
                    raise ValueError('Archivio modificato durante il reset: ' + f['path'])
                if after is None:
                    path.unlink()
                else:
                    temp = path.with_suffix('.reset-tmp')
                    with temp.open('wb') as file:
                        file.write(after); file.flush(); os.fsync(file.fileno())
                    os.replace(temp, path)
            step('file:' + f['root'] + ':' + f['path'], local)
        if self.e.journal.exists():
            def history():
                with self.e.db() as db:
                    db.execute('DELETE FROM runs WHERE project=?', (plan['project'],))
                    db.execute('DELETE FROM holds WHERE project=?', (plan['project'],))
            step('history', history)
