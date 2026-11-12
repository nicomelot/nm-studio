"""Produce native Lovelace cards for verified Home Assistant entities.

Never write Home Assistant storage, register entities, or call services.
"""

import re
import hashlib
import json

try:
    from .real_dashboard import render_dashboard
    from .entity_matcher import is_lab_entity
except ImportError:
    from real_dashboard import render_dashboard
    from entity_matcher import is_lab_entity


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug[:80] or "ambiente"


def generate(layout, entities):
    """Return a storage-mode-compatible dashboard configuration and audit report.

    Only existing, explicitly linked HA entities receive operational Tile cards.
    Unlinked or unknown devices remain in the audit report, not on the live
    dashboard: an inert mock card should never look like a working control.
    """
    widgets = [w for w in layout.get("widgets", []) if w.get('visible', True)]
    nodes = layout.get("structure", [])
    available = {e["entity_id"] for e in entities if isinstance(e, dict) and isinstance(e.get("entity_id"), str)}
    by_id = {n["id"]: n for n in nodes}

    def path(node):
        parts = []
        while node:
            parts.insert(0, node["name"])
            node = by_id.get(node.get("parent"))
        return " / ".join(parts)

    paths = [path(n) for n in nodes if n["type"] == "room" and n.get("active", True)
             and all(by_id[p].get("active", True) for p in _ancestors(n, by_id))]
    paths += layout.get("rooms", [])
    paths += [w.get("room", "Da assegnare") for w in widgets]
    rooms = list(dict.fromkeys(p for p in paths if isinstance(p, str) and p.strip()))
    if not rooms:
        rooms = ["Da assegnare"]

    overview = {"title": "Panoramica casa", "path": "panoramica", "icon": "mdi:home-outline",
                "type": "sections", "sections": []}
    reports = []
    approved = []
    for room in rooms:
        for w in widgets:
            if w.get("room", "Da assegnare") != room:
                continue
            ident = w.get("entity_id", "")
            kind = w.get("type", "")
            expected = {"light": {"light", "switch"}, "dimmer": {"light"},
                        "cover": {"cover"}, "sensor": {"sensor", "binary_sensor"},
                        "climate": {"climate"}, "fan": {"fan"},
                        "switch": {"switch"}, "button": {"button"},
                        "binary_sensor": {"binary_sensor"}, "number": {"number"}}.get(kind, set())
            compatible = bool(ident and ident.split(".", 1)[0] in expected)
            confirmed = compatible and ident in available and not is_lab_entity(ident)
            if confirmed:
                card = {"type": "tile", "entity": ident, "name": w["name"]}
                card["hold_action"] = {"action": "more-info"}
                card["tap_action"] = {"action": "more-info"}
                card["icon_tap_action"] = {"action": "more-info"}
                card["grid_options"] = {"columns": 12}
                if ident.startswith("cover."):
                    card["features"] = [{"type": "cover-open-close"}]
                elif ident.startswith("climate."):
                    card["features"] = [{"type": "climate-hvac-modes"}]
                if kind == 'switch':
                    card['icon_tap_action'] = {'action': 'toggle'}
                if kind == 'button' or w.get('command_mode') == 'off_only':
                    action = 'button.press' if kind == 'button' else ident.split('.')[0] + '.turn_off'
                    card = {'type': 'button', 'name': w['name'],
                            'icon': 'mdi:gesture-tap-button' if kind == 'button' else 'mdi:power',
                            'show_state': False, 'grid_options': {'columns': 12},
                            'tap_action': {'action': 'perform-action',
                                           'perform_action': action,
                                           'target': {'entity_id': ident}},
                            'hold_action': {'action': 'none'}, 'double_tap_action': {'action': 'none'}}
                profile = w.get('profile')
                if profile == 'filter_alarm':
                    card['icon'] = 'mdi:air-filter'
                    card['color'] = 'amber'
                elif profile == 'filter_reset':
                    card['icon'] = 'mdi:air-filter'
                    card['tap_action']['confirmation'] = {
                        'text': 'Confermi il reset dopo la pulizia o sostituzione del filtro?'}
                elif profile == 'flap_position':
                    card['features'] = [{'type': 'numeric-input', 'style': 'slider'}]
                parts = [p.strip() for p in room.split(" / ") if p.strip()]
                floor = parts[-2] if len(parts) >= 3 else "Da assegnare"
                zone = parts[-1] if len(parts) >= 3 else room
                category = {"light": "Illuminazione", "dimmer": "Illuminazione",
                            "cover": "Schermature", "climate": "Climatizzazione",
                            "sensor": "Sensori", "fan": "Ventilazione", "switch": "Altri carichi"}.get(kind, "Altri carichi")
                if profile:
                    category = 'Climatizzazione'
                elif kind == 'button' or w.get('command_mode') == 'off_only':
                    category = 'Comandi'
                approved.append({"card": card, "room": room, "floor": floor,
                                 "zone": zone, "category": category})
            else:
                reason = ("Entità LAB simulata: associa una entità reale" if is_lab_entity(ident) else
                          "Entità non assegnata" if not ident else
                          "Dominio HA incompatibile" if not compatible else "Entità non presente nell'inventario HA")
                reports.append({"room": room, "widget": w["name"], "entity_id": ident, "reason": reason})
    url_path = 'nm-studio-reale-' + hashlib.sha256(str(layout.get('project', '')).encode()).hexdigest()[:12]
    dashboard = render_dashboard(approved, url_path)
    fingerprint = hashlib.sha256(json.dumps(dashboard, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"version": 1, "read_only": True, "applied": False,
            "dashboard": dashboard, "fingerprint": fingerprint, "url_path": url_path,
            "summary": {"rooms": len({item["room"] for item in approved}),
                        "tiles": len(approved),
                        "placeholders": len(reports)},
            "warnings": reports}


def _ancestors(node, by_id):
    current = node.get("parent")
    seen = set()
    while current and current in by_id and current not in seen:
        seen.add(current)
        yield current
        current = by_id[current].get("parent")

