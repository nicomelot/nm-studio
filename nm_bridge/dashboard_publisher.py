"""Explicit Lovelace publishing and previewed updates preserving manual edits.

Never call KNX services or alter entity registries. Existing dashboard updates
require a reviewed fingerprint and a durable backup before writing.
"""

import json
import os
import re

try:
    from .lovelace_generator import generate
except ImportError:
    from lovelace_generator import generate


URL_PATH = re.compile(r"^nm-studio-[a-z0-9-]{3,52}$")
# Up to 200 zones, each with a floor, controls and history view.
MAX_VIEWS = 640


class PublishError(ValueError):
    pass


class HAWebSocket:
    def __init__(self, connection=None):
        self.connection = connection
        self.sequence = 0

    def __enter__(self):
        if self.connection is None:
            from websocket import create_connection
            token = os.environ.get("SUPERVISOR_TOKEN")
            if not token:
                raise PublishError("Token Supervisor non disponibile")
            self.connection = create_connection(
                "ws://supervisor/core/websocket", timeout=12,
                header={"Authorization": "Bearer " + token},
                http_proxy_host=None,
            )
        greeting = self._receive()
        if greeting.get("type") == "auth_required":
            self.connection.send(json.dumps({"type": "auth", "access_token": os.environ.get("SUPERVISOR_TOKEN", "")}))
            greeting = self._receive()
        if greeting.get("type") != "auth_ok":
            raise PublishError("Autenticazione WebSocket HA non riuscita")
        return self

    def __exit__(self, *_):
        self.connection.close()

    def _receive(self):
        result = json.loads(self.connection.recv())
        if not isinstance(result, dict):
            raise PublishError("Risposta WebSocket HA non valida")
        return result

    def call(self, type_, **args):
        self.sequence += 1
        command = {"id": self.sequence, "type": type_, **args}
        self.connection.send(json.dumps(command, ensure_ascii=False))
        for _ in range(20):
            response = self._receive()
            if response.get("id") != self.sequence:
                continue
            if response.get("type") != "result" or not response.get("success"):
                detail = response.get("error", {})
                message = detail.get("message", "Operazione rifiutata") if isinstance(detail, dict) else "Operazione rifiutata"
                raise PublishError("Home Assistant: " + str(message)[:180])
            return response.get("result")
        raise PublishError("Nessuna conferma da Home Assistant")


def _listed_paths(raw):
    if isinstance(raw, dict):
        raw = raw.get("dashboards", raw.get("items", []))
    if not isinstance(raw, list):
        raise PublishError("Elenco dashboard HA non riconosciuto: pubblicazione annullata")
    return {entry.get("url_path") for entry in raw if isinstance(entry, dict)}


def publish(payload, layout, entities, client_factory=HAWebSocket):
    return publish_generated(payload, generate(layout, entities), client_factory)


def publish_generated(payload, generated, client_factory=HAWebSocket):
    """Publish a server-generated preview, never a client-supplied configuration."""
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise PublishError("Conferma esplicita obbligatoria")
    url_path = payload.get("url_path")
    title = payload.get("title")
    if not isinstance(url_path, str) or not URL_PATH.fullmatch(url_path):
        raise PublishError("Percorso non valido: usa nm-studio- seguito da lettere, numeri o trattini")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 60:
        raise PublishError("Titolo dashboard non valido")
    if payload.get("expected_fingerprint") != generated["fingerprint"]:
        raise PublishError("Anteprima non aggiornata: rigenera prima di pubblicare")
    if generated["summary"]["tiles"] == 0:
        raise PublishError("Nessuna entità HA compatibile: associa almeno un dispositivo reale prima di pubblicare")
    if not 1 <= len(generated["dashboard"]["views"]) <= MAX_VIEWS:
        raise PublishError("Numero viste inatteso")
    # Rebase only generated internal navigation when a custom path is chosen.
    config = json.loads(json.dumps(generated["dashboard"]))
    original = generated.get("url_path")
    def rebase(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"navigation_path", "back_path"} and isinstance(item, str) and original and item.startswith('/' + original + '/'):
                    value[key] = '/' + url_path + item[len(original) + 1:]
                else:
                    rebase(item)
        elif isinstance(value, list):
            for item in value:
                rebase(item)
    rebase(config)
    config["title"] = title.strip()
    with client_factory() as client:
        existing = _listed_paths(client.call("lovelace/dashboards/list"))
        if url_path in existing:
            raise PublishError("Dashboard già esistente: non viene sovrascritta")
        client.call("lovelace/dashboards/create", url_path=url_path, title=title.strip(),
                    icon="mdi:floor-plan", show_in_sidebar=True, require_admin=False)
        # If save fails the empty dashboard may remain. Never silently delete
        # or retry by overwriting: report the exact path to the installer.
        try:
            client.call("lovelace/config/save", url_path=url_path, config=config)
        except Exception as exc:
            raise PublishError("Dashboard creata ma configurazione non salvata (" + url_path + "): " + str(exc)[:140]) from exc
        # Confirm a readable config; avoid claiming a successful publish on
        # an unexpected response or mismatched view structure.
        stored = client.call("lovelace/config", url_path=url_path)
        if not isinstance(stored, dict) or stored.get("views") != config["views"]:
            raise PublishError("Dashboard creata, ma verifica contenuto non riuscita: " + url_path)
    if url_path == generated.get('url_path') and url_path.startswith('nm-studio-reale-'):
        _save_baseline(url_path, config)
    return {"created": True, "url_path": url_path, "title": title.strip(),
            "summary": generated["summary"], "warnings": generated["warnings"]}



# Updating an existing real dashboard is a separate, previewed operation.
# The create-only publisher above deliberately retains its original contract.
import hashlib
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone

_UPDATE_LOCK = threading.Lock()
BACKUP_DIR = Path('/data/dashboard_backups')


def _digest(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _update_target(payload, generated):
    path = payload.get('url_path') if isinstance(payload, dict) else None
    if not isinstance(path, str) or not URL_PATH.fullmatch(path) or path != generated.get('url_path'):
        raise PublishError('Seleziona la dashboard reale generata per questo progetto')
    if not generated['summary']['tiles']:
        raise PublishError('Nessuna entità reale associata: aggiornamento annullato')
    return path


def _read_current(client, path):
    if path not in _listed_paths(client.call('lovelace/dashboards/list')):
        raise PublishError('Dashboard non presente: usa Crea nuova dashboard')
    current = client.call('lovelace/config', url_path=path)
    if not isinstance(current, dict) or not isinstance(current.get('views'), list):
        raise PublishError('Configurazione esistente non leggibile: nessuna modifica')
    return current


def _item_key(item, index):
    """Use native Lovelace identities; never add private fields to HA cards."""
    if not isinstance(item, dict):
        return ('value', json.dumps(item, sort_keys=True))
    for key in ('path', 'entity', 'heading'):
        if key in item:
            return (key, str(item[key]))
    action = item.get('tap_action', {})
    target = action.get('target', {}).get('entity_id')
    if isinstance(target, str):
        return ('entity', target)
    if action.get('navigation_path'):
        return ('navigation', action['navigation_path'])
    if item.get('name') or item.get('title'):
        return ('name', item.get('name', item.get('title')))
    if item.get('cards') and item['cards'][0].get('heading'):
        return ('section', item['cards'][0]['heading'])
    return ('position', index)


def _merge_dashboard(base, current, new):
    """Three-way merge. A manual edit or deletion wins a conflicting change."""
    if current == base:
        return new
    if new == base or current == new:
        return current
    if all(isinstance(v, dict) for v in (base, current, new)):
        if ('cards' in current and 'sections' in new) or ('sections' in current and 'cards' in new):
            return current  # Preserve a manually chosen masonry/sections layout.
        result = dict(current)
        for key, value in new.items():
            if key not in current:
                if key not in base:
                    result[key] = value
            elif key in base:
                result[key] = _merge_dashboard(base[key], current[key], value)
            elif isinstance(value, list) and isinstance(current[key], list):
                result[key] = _merge_dashboard([], current[key], value)
        for key in base.keys() - new.keys():
            if key in current and current[key] == base[key]:
                result.pop(key)
        return result
    if all(isinstance(v, list) for v in (base, current, new)):
        def keyed(items):
            pairs = [(_item_key(item, i), item) for i, item in enumerate(items)]
            return dict(pairs) if len(dict(pairs)) == len(pairs) else None
        b, c, n = keyed(base), keyed(current), keyed(new)
        # Ambiguous duplicate cards: preserve the whole manually edited list.
        if any(v is None for v in (b, c, n)):
            return current
        result = []
        for key, item in c.items():
            if key in b and key not in n and item == b[key]:
                continue
            if key in b and key in n:
                item = _merge_dashboard(b[key], item, n[key])
            elif key in n and isinstance(item, dict) and any(k in item for k in ('cards', 'sections')):
                # Legacy dashboard without a baseline: keep existing values,
                # but discover additions inside views and sections.
                item = _merge_dashboard({}, item, n[key])
            result.append(item)
        result.extend(item for key, item in n.items() if key not in c and key not in b)
        return result
    return current


def _baseline_file(path, backup_dir=None):
    return (Path(backup_dir) if backup_dir is not None else BACKUP_DIR) / 'baselines' / (path + '.json')


def _read_baseline(path, backup_dir=None):
    try:
        value = json.loads(_baseline_file(path, backup_dir).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_baseline(path, config, backup_dir=None):
    target = _baseline_file(path, backup_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as stream:
        json.dump(config, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, target)


def _replacement(generated, current, backup_dir=None):
    config = _merge_dashboard(_read_baseline(generated['url_path'], backup_dir), current,
                              generated['dashboard'])
    config = json.loads(json.dumps(config))
    # An explicit off-only conversion also applies to native shortcuts already
    # placed by the installer. Keep their position, label and icon, not a toggle.
    off_controls = {}
    def collect(value):
        if isinstance(value, dict):
            action = value.get('tap_action', {})
            if value.get('type') == 'button' and action.get('perform_action') in ('light.turn_off', 'switch.turn_off'):
                off_controls[action['target']['entity_id']] = value
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(generated['dashboard'])
    def constrain(value):
        if isinstance(value, dict):
            ident = value.get('entity') or value.get('tap_action', {}).get('target', {}).get('entity_id')
            if value.get('type') in ('tile', 'button') and isinstance(ident, str) and ident in off_controls:
                appearance = {k: value[k] for k in ('name', 'icon', 'grid_options') if k in value}
                value.clear()
                value.update(json.loads(json.dumps(off_controls[ident])))
                value.update(appearance)
            for child in value.values():
                constrain(child)
        elif isinstance(value, list):
            for child in value:
                constrain(child)
    constrain(config)
    # Keep the existing dashboard title; its sidebar metadata is not changed.
    if 'title' in current:
        config['title'] = current['title']
    return config


def preview_update(payload, layout, entities, client_factory=HAWebSocket, backup_dir=None):
    generated = generate(layout, entities)
    path = _update_target(payload, generated)
    with client_factory() as client:
        current = _read_current(client, path)
    config = _replacement(generated, current, backup_dir)
    return {'url_path': path, 'expected_current': _digest(current),
            'expected_fingerprint': generated['fingerprint'],
            'dashboard': config, 'previous_dashboard': current,
            'changed': current != config, 'old_views': len(current['views']),
            'new_views': len(config['views']), 'summary': generated['summary'],
            'warnings': generated['warnings'],
            'notice': 'Le personalizzazioni manuali vengono conservate, anche in caso di conflitto. Le funzioni non personalizzate vengono aggiornate quando è disponibile una versione precedente di riferimento. Controlla il confronto; viene salvato anche un backup.'}


def update_existing(payload, layout, entities, client_factory=HAWebSocket, backup_dir=None):
    if not isinstance(payload, dict) or payload.get('confirm') is not True:
        raise PublishError('Conferma esplicita obbligatoria')
    generated = generate(layout, entities)
    path = _update_target(payload, generated)
    if payload.get('expected_fingerprint') != generated['fingerprint']:
        raise PublishError('Anteprima non aggiornata: ripeti il confronto')
    with _UPDATE_LOCK, client_factory() as client:
        current = _read_current(client, path)
        if payload.get('expected_current') != _digest(current):
            raise PublishError('Dashboard modificata dopo il confronto: ripeti anteprima')
        config = _replacement(generated, current, backup_dir)
        if current == config:
            _save_baseline(path, generated['dashboard'], backup_dir)
            return {'updated': False, 'unchanged': True, 'url_path': path}
        directory = Path(backup_dir) if backup_dir is not None else BACKUP_DIR
        directory.mkdir(parents=True, exist_ok=True)
        # Exclusive file, flush and fsync before any write to Home Assistant.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json',
                                         prefix=path+'-', dir=directory, delete=False) as stream:
            json.dump({'url_path': path, 'created_at': datetime.now(timezone.utc).isoformat(),
                       'fingerprint': _digest(current), 'config': current}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
            backup = Path(stream.name).name
        # Narrow the race window for changes from HA's own editor.
        if _digest(client.call('lovelace/config', url_path=path)) != _digest(current):
            raise PublishError('Dashboard cambiata durante il backup: nessuna scrittura')
        try:
            client.call('lovelace/config/save', url_path=path, config=config)
            stored = client.call('lovelace/config', url_path=path)
            if stored != config:
                raise PublishError('Il contenuto riletto non coincide con la configurazione inviata')
            _save_baseline(path, generated['dashboard'], backup_dir)
        except Exception as exc:
            raise PublishError('Aggiornamento non verificato. Backup disponibile: '+backup+
                               '. Controlla la dashboard prima di riprovare. '+str(exc)[:140]) from exc
    return {'updated': True, 'url_path': path, 'backup': backup,
            'previous_dashboard': current, 'summary': generated['summary']}
