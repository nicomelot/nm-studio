"""Dedicated virtual dashboard; never reads or writes the real widget layout."""

import hashlib
import json
import os
import threading
from pathlib import Path
from datetime import datetime, timezone

UPDATE_LOCK = threading.RLock()

try:
    from .lab_devices import build
    from .dashboard_publisher import publish_generated, HAWebSocket
except ImportError:
    from lab_devices import build
    from dashboard_publisher import publish_generated, HAWebSocket


def _location(room):
    """Short display labels never replace the complete room identity."""
    parts = [p.strip() for p in room.split('/') if p.strip()]
    if len(parts) >= 3:
        return tuple(parts[:2]), ' / '.join(parts[2:])
    if len(parts) == 2:
        if parts[1].lower().startswith('piano ') or parts[1].lower() in {'interrato', 'seminterrato', 'terra', 'primo', 'secondo'}:
            return tuple(parts), 'Generali'
        return (parts[0], 'Zone'), parts[1]
    return (), room


def _floor_name(key):
    if not key:
        return 'Altre zone'
    name = key[-1]
    if name.lower().startswith('piano '):
        name = name[6:]
    return name.capitalize() if name.isupper() else name


def _room_icon(name):
    for words, icon in [(('bagno', 'wellness'), 'mdi:shower'),
                        (('camera',), 'mdi:bed-outline'),
                        (('cucina',), 'mdi:silverware-fork-knife'),
                        (('garage',), 'mdi:garage'),
                        (('soggiorno', 'sala'), 'mdi:sofa-outline'),
                        (('ufficio',), 'mdi:desk'),
                        (('palestra',), 'mdi:dumbbell')]:
        if any(word in name.lower() for word in words):
            return icon
    return 'mdi:door-open'


def preview(payload, entities):
    plan = build(payload)
    inventory = {e['entity_id']: e for e in entities if isinstance(e, dict) and 'entity_id' in e}
    rooms, categories, controls, warnings, total = {}, {}, {}, [], 0
    for item in plan['manifest']:
        ident = item['entity_id']
        entity = inventory.get(ident)
        if not entity or entity.get('state') in ('unknown', 'unavailable') and item['kind'] != 'scene':
            warnings.append({'entity_id': ident, 'reason': 'Entità virtuale assente o non disponibile; verifica configurazione e riavvio HA'})
            continue
        card = {'type': 'tile', 'entity': ident, 'name': item['name'],
                'grid_options': {'columns': 12},
                'tap_action': {'action': 'more-info'},
                'icon_tap_action': {'action': 'more-info'},
                'hold_action': {'action': 'more-info'}}
        rooms.setdefault(item['room'], []).append(card)
        category = {'light': 'Luci', 'dimmer': 'Luci', 'cover': 'Motorizzazioni',
                    'climate': 'Clima', 'scene': 'Scene'}.get(item['kind'], 'Sensori')
        categories.setdefault(category, {}).setdefault(item['room'], []).append(card)
        for control in item['controls']:
            if control in inventory:
                controls.setdefault(item['room'], []).append({'entity': control, 'name': item['name']})
            else:
                warnings.append({'entity_id': control, 'reason': 'Ingresso simulato assente'})
        total += 1
    url_path = 'nm-studio-lab-' + plan['project'][:12] + '-v2'

    def route(prefix, identity):
        return prefix + '-' + hashlib.sha256(identity.encode()).hexdigest()[:12]

    def button(title, path, icon='mdi:arrow-right'):
        return {'type': 'button', 'name': title, 'icon': icon, 'icon_height': '32px',
                'grid_options': {'columns': 12, 'rows': 2},
                'tap_action': {'action': 'navigate', 'navigation_path': '/' + url_path + '/' + path}}

    def view(title, path, sections, parent=None):
        result = {'title': title, 'path': path, 'type': 'sections', 'max_columns': 3, 'sections': sections}
        if parent:
            result.update(subview=True, back_path='/' + url_path + '/' + parent)
        return result

    def grid(cards, title=None):
        headings = [{'type': 'heading', 'heading': title, 'heading_style': 'title'}] if title else []
        return {'type': 'grid', 'cards': headings + cards}

    floors, details = {}, []
    for room in rooms:
        key, label = _location(room)
        floors.setdefault(key, []).append(room)
    buildings = {key[0] for key in floors if key}

    def floor_title(key):
        name = _floor_name(key)
        return key[0] + ' · ' + name if key and len(buildings) > 1 else name

    def floor_order(key):
        ranks = {'interrato': 0, 'seminterrato': 1, 'terra': 2, 'primo': 3, 'secondo': 4}
        return (key[0] if key else '~', ranks.get(_floor_name(key).lower(), 5), _floor_name(key))

    floor_links = []
    for key in sorted(floors, key=floor_order):
        floor_path = route('piano', json.dumps(key))
        floor_links.append(button(floor_title(key), floor_path, 'mdi:home-floor-0'))
        zone_links = []
        for room in sorted(floors[key]):
            label = _location(room)[1]
            path = route('stanza', room)
            zone_links.append(button(label, path, _room_icon(label)))
            sections = [grid(grouped[room], category) for category, grouped in categories.items() if room in grouped]
            history = ['sensor.' + c['entity'].split('.', 1)[1] + '_temperature'
                       if c['entity'].startswith('climate.') else c['entity']
                       for c in rooms[room] if not c['entity'].startswith('input_button.')]
            if history:
                history_path = route('storico', room)
                sections.append(grid([button('Storico 48 ore', history_path, 'mdi:chart-line')]))
                details.append(view(label + ' · Storico', history_path, [grid([
                    {'type': 'markdown', 'content': 'Storico 48 ore. Richiede Recorder attivo; i periodi non registrati non sono ricostruibili.'},
                    *[{'type': 'history-graph', 'entities': history[i:i+12], 'hours_to_show': 48}
                      for i in range(0, len(history), 12)]])], path))
            details.append(view(label, path, sections, floor_path))
        details.append(view(floor_title(key), floor_path,
                            [grid(zone_links[i:i+6]) for i in range(0, len(zone_links), 6)], 'ambienti'))

    function_links = []
    for category, grouped in categories.items():
        path = route('funzione', category)
        function_links.append(button(category, path))
        sections = []
        for key in sorted(floors, key=floor_order):
            for room in sorted(floors[key]):
                if room in grouped:
                    sections.append(grid(grouped[room], floor_title(key) + ' · ' + _location(room)[1]))
        details.append(view(category, path, sections, 'funzioni'))

    lab_sections = [grid([{'type': 'markdown', 'content': '## Strumenti LAB\nValori simulati, nessun comando KNX. Posizioni istantanee; scene: solo richiamo.'}])]
    for room, rows in sorted(controls.items()):
        key, label = _location(room)
        lab_sections.append(grid([{'type': 'entities', 'entities': rows, 'show_header_toggle': False}],
                                 floor_title(key) + ' · ' + label))
    details.append(view('Strumenti LAB', 'strumenti-lab', lab_sections, 'panoramica'))
    overview = []
    for category, states, title in [('Luci', ['on'], 'Luci accese'),
                                     ('Motorizzazioni', ['open', 'opening'], 'Motorizzazioni aperte')]:
        ids = [{'entity': c['entity'], 'name': c['name']} for cards in categories.get(category, {}).values() for c in cards]
        if ids:
            overview.append({'type': 'entity-filter', 'entities': ids, 'state_filter': states,
                             'show_empty': False, 'card': {'type': 'entities', 'title': title, 'show_header_toggle': False}})
    dashboard = {'title': 'NM Control LAB', 'views': [
        view('Home', 'panoramica', [grid([
            {'type': 'markdown', 'content': '# La casa\nLaboratorio virtuale · ' + str(total) + ' entità'},
            button('Ambienti', 'ambienti', 'mdi:floor-plan'),
            button('Funzioni', 'funzioni', 'mdi:lightbulb-group-outline'),
            button('Strumenti LAB', 'strumenti-lab', 'mdi:flask-outline')]),
            *([grid(overview)] if overview else [])]),
        view('Ambienti', 'ambienti', [grid(floor_links, 'Scegli il piano')]),
        view('Funzioni', 'funzioni', [grid(function_links, 'Scegli la categoria')]), *details]}
    return {'dashboard': dashboard, 'fingerprint': hashlib.sha256(json.dumps(dashboard, sort_keys=True).encode()).hexdigest(),
            'summary': {'tiles': total, 'rooms': len(rooms), 'placeholders': len(warnings)}, 'warnings': warnings,
            'url_path': url_path, 'knx_traffic': False}


def publish(payload, entities, client_factory=HAWebSocket):
    generated = preview(payload, entities)
    if generated["warnings"]:
        raise ValueError("Entità virtuali mancanti: completa il caricamento HA prima di pubblicare")
    request = {"confirm": payload.get("confirm"), "expected_fingerprint": payload.get("expected_fingerprint"),
               "url_path": generated["url_path"], "title": "NM Control LAB"}
    return publish_generated(request, generated, client_factory)


def inspect_existing(payload, entities, client_factory=HAWebSocket):
    generated = preview(payload, entities)
    with client_factory() as client:
        dashboards = client.call('lovelace/dashboards/list')
        if not isinstance(dashboards, list):
            raise ValueError('Elenco dashboard non riconosciuto')
        if not any(d.get('url_path') == generated['url_path'] for d in dashboards):
            return {'exists': False}
        current = client.call('lovelace/config', url_path=generated['url_path'])
    if not isinstance(current, dict) or not isinstance(current.get('views'), list):
        raise ValueError('Dashboard esistente non riconosciuta')
    return {'exists': True, 'fingerprint': hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()}


def update(payload, entities, client_factory=HAWebSocket, backup_root=None):
    if not isinstance(payload, dict):
        raise ValueError('Richiesta aggiornamento non valida')
    if payload.get('confirm') is not True:
        raise ValueError('Conferma aggiornamento dashboard obbligatoria')
    generated = preview(payload, entities)
    if generated['warnings'] or not generated['summary']['tiles']:
        raise ValueError('Entità mancanti: aggiornamento dashboard bloccato')
    if payload.get('expected_fingerprint') != generated['fingerprint']:
        raise ValueError('Anteprima non aggiornata')
    with UPDATE_LOCK, client_factory() as client:
        current = client.call('lovelace/config', url_path=generated['url_path'])
        if not isinstance(current, dict) or not isinstance(current.get('views'), list):
            raise ValueError('Dashboard esistente non riconosciuta')
        fingerprint = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
        if fingerprint != payload.get('expected_existing_fingerprint'):
            raise ValueError('Dashboard modificata: ripeti la verifica')
        root = Path(backup_root or '/data/nm_lab_dashboard_backups')
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = root / (generated['url_path'] + '-' + stamp + '.json')
        with backup.open('x', encoding='utf-8') as stream:
            json.dump(current, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        client.call('lovelace/config/save', url_path=generated['url_path'], config=generated['dashboard'])
        stored = client.call('lovelace/config', url_path=generated['url_path'])
        if not isinstance(stored, dict) or stored.get('views') != generated['dashboard']['views']:
            raise ValueError('Aggiornamento inviato ma verifica fallita; backup disponibile in ' + str(backup))
    return {'updated': True, 'url_path': generated['url_path'], 'backup': str(backup)}
