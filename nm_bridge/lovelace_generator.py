"""Produce an inert Lovelace dashboard draft from saved NM Studio widgets.

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
    Unlinked or unknown devices become harmless Markdown placeholders.
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

    view = {"title": "NM Studio", "path": "nm-studio", "type": "sections", "sections": []}
    reports = []
    for room in rooms:
        cards = []
        for w in widgets:
            if w.get("room", "Da assegnare") != room:
                continue
            ident = w.get("entity_id", "")
            kind = w.get("type", "")
            expected = {"light": {"light", "switch"}, "dimmer": {"light"},
                        "cover": {"cover"}}.get(kind, set())
            compatible = bool(ident and ident.split(".", 1)[0] in expected)
            confirmed = compatible and ident in available
            if confirmed:
                cards.append({"type": "tile", "entity": ident, "name": w["name"]})
            else:
                reason = ("Entità non assegnata" if not ident else
                          "Dominio HA incompatibile" if not compatible else "Entità non presente nell'inventario HA")
                # Markdown is display-only: no tap_action, script, service or bus traffic.
                cards.append({"type": "markdown", "content": "**" + w["name"] + "**\n\n⚠ " + reason})
                reports.append({"room": room, "widget": w["name"], "entity_id": ident, "reason": reason})
        if cards:
            view["sections"].append({"type": "grid", "title": room, "cards": cards})
    if not view["sections"]:
        view["sections"].append({"type": "grid", "title": "Da configurare", "cards": [
            {"type": "markdown", "content": "Nessuna entità HA associata. Completa i widget in NM Studio."}]})
    dashboard = {"title": "NM Studio · Bozza", "views": [view]}
    fingerprint = hashlib.sha256(json.dumps(dashboard, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"version": 1, "read_only": True, "applied": False,
            "dashboard": dashboard, "fingerprint": fingerprint,
            "summary": {"rooms": len(view["sections"]),
                        "tiles": sum(c["type"] == "tile" for s in view["sections"] for c in s["cards"]),
                        "placeholders": len(reports)},
            "warnings": reports}


def _ancestors(node, by_id):
    current = node.get("parent")
    seen = set()
    while current and current in by_id and current not in seen:
        seen.add(current)
        yield current
        current = by_id[current].get("parent")
