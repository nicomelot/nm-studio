"""Produce native Lovelace cards for verified Home Assistant entities.

Never write Home Assistant storage, register entities, or call services.
"""

import re
import hashlib
import json


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug[:80] or "ambiente"


def generate(layout, entities):
    """Return a storage-mode-compatible dashboard configuration and audit report.

    Only existing, explicitly linked HA entities receive operational Tile cards.
    Unlinked or unknown devices remain in the audit report, not on the live
    dashboard: an inert mock card should never look like a working control.
    """
    widgets = layout.get("widgets", [])
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
                        "switch": {"switch"}}.get(kind, set())
            compatible = bool(ident and ident.split(".", 1)[0] in expected)
            confirmed = compatible and ident in available
            if confirmed:
                card = {"type": "tile", "entity": ident, "name": w["name"]}
                if ident.startswith("cover."):
                    card["features"] = [{"type": "cover-open-close"}]
                elif ident.startswith("climate."):
                    card["features"] = [{"type": "climate-hvac-modes"}]
                parts = [p.strip() for p in room.split(" / ") if p.strip()]
                floor = parts[-2] if len(parts) >= 3 else "Da assegnare"
                zone = parts[-1] if len(parts) >= 3 else room
                category = {"light": "Illuminazione", "dimmer": "Illuminazione",
                            "cover": "Schermature", "climate": "Climatizzazione",
                            "sensor": "Sensori", "fan": "Ventilazione", "switch": "Altri carichi"}.get(kind, "Altri carichi")
                approved.append({"card": card, "room": room, "floor": floor,
                                 "zone": zone, "category": category})
            else:
                reason = ("Entità non assegnata" if not ident else
                          "Dominio HA incompatibile" if not compatible else "Entità non presente nell'inventario HA")
                reports.append({"room": room, "widget": w["name"], "entity_id": ident, "reason": reason})
    # These are actual HA tile cards linked to verified entity IDs. No sample
    # values, simulated controls or placeholder entities are ever rendered.
    categories = ("Illuminazione", "Climatizzazione", "Schermature", "Ventilazione",
                  "Sensori", "Altri carichi")
    for category in categories:
        cards = [item["card"] for item in approved if item["category"] == category]
        if cards:
            overview["sections"].append({"type": "grid", "title": category,
                                         "cards": cards[:4]})
    views = [overview]
    icons = {"Illuminazione": "mdi:lightbulb-group-outline", "Climatizzazione": "mdi:thermostat",
             "Schermature": "mdi:blinds", "Ventilazione": "mdi:fan",
             "Sensori": "mdi:access-point", "Altri carichi": "mdi:power-socket-eu"}
    paths = {"Illuminazione": "illuminazione", "Climatizzazione": "climatizzazione",
             "Schermature": "schermature", "Ventilazione": "ventilazione",
             "Sensori": "sensori", "Altri carichi": "carichi"}
    for category in categories:
        scoped = [item for item in approved if item["category"] == category]
        if not scoped:
            continue
        section_keys = sorted({(item["floor"], item["zone"]) for item in scoped})
        sections = [{"type": "grid", "title": f"{floor} · {zone}",
                     "cards": [item["card"] for item in scoped
                               if (item["floor"], item["zone"]) == (floor, zone)]}
                    for floor, zone in section_keys]
        views.append({"title": category, "path": paths[category], "icon": icons[category],
                      "type": "sections", "sections": sections})
    if approved:
        views.append({"title": "Ambienti", "path": "ambienti", "icon": "mdi:floor-plan",
                      "type": "sections", "sections": [
                          {"type": "grid", "title": room,
                           "cards": [item["card"] for item in approved if item["room"] == room]}
                          for room in rooms if any(item["room"] == room for item in approved)]})
    dashboard = {"title": "NM Control", "views": views}
    fingerprint = hashlib.sha256(json.dumps(dashboard, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"version": 1, "read_only": True, "applied": False,
            "dashboard": dashboard, "fingerprint": fingerprint,
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
