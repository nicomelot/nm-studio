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
    rooms, warnings, total = {}, [], 0
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
        for control in item["controls"]:
            if control in inventory:
                group.append({"type": "entities", "entities": [control], "title": "Valore simulato - " + item["name"]})
            else:
                warnings.append({"entity_id": control, "reason": "Ingresso simulato assente"})
        total += 1
    notice = {"type": "markdown", "content": "## Laboratorio virtuale\nNessun comando KNX. Posizioni istantanee; scene: solo richiamo; sensori manuali."}
    dashboard = {"title": "NM Control LAB", "views": [
        {"title": "Panoramica casa", "path": "panoramica", "type": "sections", "sections": [
            {"type": "grid", "cards": [notice]},
            *[{"type": "grid", "title": room, "cards": cards} for room, cards in rooms.items()]]},
        {"title": "Ambienti", "path": "ambienti", "type": "sections", "sections": [
            {"type": "grid", "title": room, "cards": cards} for room, cards in rooms.items()]}]}
    return {"dashboard": dashboard, "fingerprint": hashlib.sha256(json.dumps(dashboard, sort_keys=True).encode()).hexdigest(),
            "summary": {"tiles": total, "rooms": len(rooms), "placeholders": len(warnings)}, "warnings": warnings,
            "url_path": "nm-studio-lab-" + plan["project"][:12], "knx_traffic": False}


def publish(payload, entities, client_factory=HAWebSocket):
    generated = preview(payload, entities)
    if generated["warnings"]:
        raise ValueError("Entità virtuali mancanti: completa il caricamento HA prima di pubblicare")
    request = {"confirm": payload.get("confirm"), "expected_fingerprint": payload.get("expected_fingerprint"),
               "url_path": generated["url_path"], "title": "NM Control LAB"}
    return publish_generated(request, generated, client_factory)
