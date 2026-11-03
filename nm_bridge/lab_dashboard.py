"""Dedicated virtual dashboard; never reads or writes the real widget layout."""

import hashlib
import json

try:
    from .lab_devices import build
    from .dashboard_publisher import publish_generated, HAWebSocket
except ImportError:
    from lab_devices import build
    from dashboard_publisher import publish_generated, HAWebSocket


def preview(payload, entities):
    plan = build(payload)
    inventory = {e["entity_id"]: e for e in entities if isinstance(e, dict) and "entity_id" in e}
    rooms, categories, warnings, total = {}, {}, [], 0
    for item in plan["manifest"]:
        ident = item["entity_id"]
        entity = inventory.get(ident)
        if not entity or entity.get("state") in ("unknown", "unavailable") and item["kind"] != "scene":
            warnings.append({"entity_id": ident, "reason": "Entità virtuale assente o non disponibile; verifica configurazione e riavvio HA"})
            continue
        card = {"type": "tile", "entity": ident, "name": "LAB " + item["name"]}
        if item["kind"] == "cover":
            card["features"] = [{"type": "cover-open-close"}, {"type": "cover-position"}]
        elif item["kind"] == "dimmer":
            card["features"] = [{"type": "light-brightness"}]
        elif item["kind"] == "scene":
            card["tap_action"] = {"action": "perform-action", "perform_action": "input_button.press", "target": {"entity_id": ident}}
        group = rooms.setdefault(item["room"], [])
        group.append(card)
        category = {"light": "Luci", "dimmer": "Luci", "cover": "Motorizzazioni",
                    "climate": "Clima", "scene": "Scene"}.get(item["kind"], "Sensori")
        categories.setdefault(category, {}).setdefault(item["room"], []).append(card)
        for control in item["controls"]:
            if control in inventory:
                group.append({"type": "entities", "entities": [control], "title": "Valore simulato - " + item["name"]})
            else:
                warnings.append({"entity_id": control, "reason": "Ingresso simulato assente"})
        total += 1
    notice = {"type": "markdown", "content": "## Laboratorio virtuale\nNessun comando KNX. Posizioni istantanee; scene: solo richiamo; sensori manuali."}
    # Keep the previous dashboard and any customer customizations intact.
    url_path = "nm-studio-lab-" + plan["project"][:12] + "-v2"
    def button(title, path, icon="mdi:arrow-right"):
        return {"type": "button", "name": title, "icon": icon,
                "tap_action": {"action": "navigate", "navigation_path": "/" + url_path + "/" + path}}
    def view(title, path, sections, parent=None):
        result = {"title": title, "path": path, "type": "sections", "sections": sections}
        if parent:
            result.update(subview=True, back_path="/" + url_path + "/" + parent)
        return result
    def grid(cards, title=None):
        return {"type": "grid", "cards": cards, **({"title": title} if title else {})}
    room_links, details = {}, []
    for i, (room, cards) in enumerate(sorted(rooms.items())):
        path = "stanza-" + str(i)
        floor = room.rsplit(" / ", 1)[0] if " / " in room else "Ambienti"
        room_links.setdefault(floor, []).append(button(room, path, "mdi:door"))
        details.append(view(room, path, [grid(cards)], "ambienti"))
    function_links = []
    for i, (category, grouped) in enumerate(categories.items()):
        path = "funzione-" + str(i)
        function_links.append(button(category, path))
        links = []
        for j, (room, cards) in enumerate(sorted(grouped.items())):
            filtered = path + "-stanza-" + str(j)
            links.append(button(room, filtered, "mdi:filter"))
            details.append(view(category + " - " + room, filtered, [grid(cards)], path))
        details.append(view(category, path, [grid(links, "Filtra per ambiente"),
            *[grid(cards, room) for room, cards in sorted(grouped.items())]], "funzioni"))
    lights = [c["entity"] for cards in categories.get("Luci", {}).values() for c in cards]
    covers = [c["entity"] for cards in categories.get("Motorizzazioni", {}).values() for c in cards]
    climates = [c["entity"] for cards in categories.get("Clima", {}).values() for c in cards]
    overview = []
    for ids, states, title in [(lights, ["on"], "Luci accese"), (covers, ["open", "opening"], "Motorizzazioni aperte")]:
        if ids:
            overview.append({"type": "entity-filter", "entities": ids, "state_filter": states,
                             "show_empty": False, "card": {"type": "entities", "title": title}})
    if climates:
        overview.append({"type": "entities", "entities": climates, "title": "Clima"})
    dashboard = {"title": "NM Control LAB", "views": [
        view("Home", "panoramica", [grid([notice, button("Ambienti", "ambienti"), button("Funzioni", "funzioni")]),
                                     *([grid(overview)] if overview else [])]),
        view("Ambienti", "ambienti", [grid(cards, floor) for floor, cards in room_links.items()]),
        view("Funzioni", "funzioni", [grid(function_links)]), *details]}
    return {"dashboard": dashboard, "fingerprint": hashlib.sha256(json.dumps(dashboard, sort_keys=True).encode()).hexdigest(),
            "summary": {"tiles": total, "rooms": len(rooms), "placeholders": len(warnings)}, "warnings": warnings,
            "url_path": url_path, "knx_traffic": False}


def publish(payload, entities, client_factory=HAWebSocket):
    generated = preview(payload, entities)
    if generated["warnings"]:
        raise ValueError("Entità virtuali mancanti: completa il caricamento HA prima di pubblicare")
    request = {"confirm": payload.get("confirm"), "expected_fingerprint": payload.get("expected_fingerprint"),
               "url_path": generated["url_path"], "title": "NM Control LAB"}
    return publish_generated(request, generated, client_factory)
