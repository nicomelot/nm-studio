"""Synchronize reviewed ETS rooms with HA registries, without bus commands.

Existing explicit entity assignments are preserved. Mapping IDs survive renames;
this operation never deletes or renames HA areas, floors or entities.
"""
import json
import os
import tempfile
from pathlib import Path

try:
    from .dashboard_publisher import HAWebSocket
    from .widget_layout import LAYOUT_LOCK, read_layout, WIDGET_PATH
    from .missing_ha_generator import fingerprint
except ImportError:
    from dashboard_publisher import HAWebSocket
    from widget_layout import LAYOUT_LOCK, read_layout, WIDGET_PATH
    from missing_ha_generator import fingerprint


def save_mapping(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
            temporary = f.name
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def sync(layout, request, connection_factory=HAWebSocket, mapping_path=None):
    if not isinstance(request, dict) or request.get('confirm') is not True or request.get('source_fingerprint') != fingerprint(layout):
        raise ValueError('Conferma e configurazione aggiornata richieste per sincronizzare le stanze')
    path = Path(mapping_path) if mapping_path else WIDGET_PATH.parent / 'native_area_mapping.json'
    mapping = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    project = mapping.setdefault(layout['project'], {})
    nodes = {n['id']: n for n in layout.get('structure', [])}
    paths, active = {}, {}
    for ident, node in nodes.items():
        parent = node.get('parent')
        paths[ident] = (paths[parent] + ' / ' if parent else '') + node['name']
        active[ident] = node.get('active', True) and (active.get(parent, True))
    notices, assigned = [], 0
    with connection_factory() as ws:
        areas = ws.call('config/area_registry/list')
        floors = ws.call('config/floor_registry/list')
        if not isinstance(areas, list) or not isinstance(floors, list):
            raise ValueError('Registri Home Assistant non disponibili')
        resolved = {}
        for ident, node in nodes.items():
            kind = node['type']
            if kind not in ('room', 'floor') or not active[ident]:
                continue
            records, id_key, registry = (areas, 'area_id', 'area') if kind == 'room' else (floors, 'floor_id', 'floor')
            record = next((r for r in records if r[id_key] == project.get(ident)), None)
            # Disambiguate equal room/floor names in different buildings or floors.
            twins = [n for n in nodes.values() if n['type'] == kind and n['name'].casefold() == node['name'].casefold()]
            name = paths[ident] if len(twins) > 1 else node['name']
            wanted_floor = resolved.get(node.get('parent')) if kind == 'room' and nodes.get(node.get('parent'), {}).get('type') == 'floor' else None
            if kind == 'room' and nodes.get(node.get('parent'), {}).get('type') == 'floor' and not wanted_floor:
                notices.append(name + ': piano non risolto, stanza da verificare')
                continue
            if record is None:
                matches = [r for r in records if r['name'].casefold() == name.casefold()]
                if len(matches) > 1:
                    notices.append(name + ': più corrispondenze HA, associazione da verificare')
                    continue
                if matches:
                    record = matches[0]
                    if kind == 'room' and record.get('floor_id') != wanted_floor:
                        notices.append(name + ': piano HA diverso, mantenuto invariato')
                        continue
                else:
                    args = {'name': name}
                    if wanted_floor:
                        args['floor_id'] = wanted_floor
                    record = ws.call(f'config/{registry}_registry/create', **args)
                    records.append(record)
                project[ident] = record[id_key]
                save_mapping(path, mapping)
            resolved[ident] = record[id_key]
        room_ids = {paths[i]: area for i, area in resolved.items() if nodes[i]['type'] == 'room'}
        for widget in layout.get('widgets', []):
            entity, area = widget.get('entity_id'), room_ids.get(widget.get('room'))
            if not entity or not area:
                continue
            record = ws.call('config/entity_registry/get', entity_id=entity)
            if not isinstance(record, dict):
                notices.append(entity + ': entità non presente nel registro')
                continue
            if record.get('area_id') and record['area_id'] != area:
                notices.append(entity + ': assegnazione HA esistente conservata')
                continue
            if record.get('area_id') != area:
                ws.call('config/entity_registry/update', entity_id=entity, area_id=area)
                assigned += 1
    return {'rooms': len(room_ids), 'assigned': assigned, 'notices': notices, 'bus_commands': False}


def synchronize_saved(request):
    with LAYOUT_LOCK:
        return sync(read_layout(), request)
