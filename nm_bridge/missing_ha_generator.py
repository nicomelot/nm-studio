"""Safe export of KNX HA YAML drafts for widgets without a known entity link.

The Home Assistant state inventory cannot prove that a group address is not
already configured. Never activate this draft without installer inspection.
"""

try:
    from .ha_generator import generate
    from .widget_layout import validate as validate_layout
except ImportError:
    from ha_generator import generate
    from widget_layout import validate as validate_layout

import hashlib
import json


def fingerprint(layout):
    return hashlib.sha256(json.dumps(layout, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def preview(layout, inventory):
    known_ids = {e.get("entity_id") for e in inventory}
    missing = []
    skipped = []
    for index, widget in enumerate(layout.get("widgets", [])):
        linked = widget.get("entity_id", "")
        if linked and linked in known_ids:
            skipped.append({"index": index, "name": widget.get("name", ""),
                            "reason": "Entità HA collegata e presente: esclusa dalla bozza"})
        elif linked:
            skipped.append({"index": index, "name": widget.get("name", ""),
                            "reason": "Associazione HA salvata ma entità non disponibile: verificare manualmente"})
        else:
            missing.append(widget)
    filtered = {**layout, "widgets": missing}
    generated = generate(filtered)
    generated["format"] = "nm-studio-missing-ha-knx-draft"
    generated["skipped"] = skipped
    generated["total_widgets"] = len(layout.get("widgets", []))
    generated["eligible_widgets"] = len(missing)
    generated["source_fingerprint"] = fingerprint(layout)
    generated["devices"] = [{"index": index, "type": widget["type"], "name": widget["name"],
                              "room": widget.get("room", "Da assegnare"),
                              "fields": dict(widget["fields"]), "approved": False}
                             for index, widget in enumerate(layout.get("widgets", []))
                             if not widget.get("entity_id")]
    generated["limitations"] = [
        "Il solo inventario degli stati HA non rileva tutti i GA già configurati: controllare i duplicati nell'integrazione KNX.",
        "Nomi, DPT e indirizzi devono essere verificati nell'ETS originale prima dell'applicazione.",
        "Questa bozza non crea o attiva entità, non modifica Home Assistant e non invia telegrammi KNX.",
    ]
    return generated


def review(layout, request):
    """Generate an unsaved YAML draft from explicit installer selections."""
    if not isinstance(request, dict) or request.get("source_fingerprint") != fingerprint(layout):
        raise ValueError("Saved KNX widgets changed; run analysis again")
    selection = request.get("devices")
    if not isinstance(selection, list) or len(selection) > 200:
        raise ValueError("Invalid device review")
    approved = []
    indices = set()
    for item in selection:
        if not isinstance(item, dict) or type(item.get("index")) is not int:
            raise ValueError("Invalid device review item")
        index = item["index"]
        if index < 0 or index >= len(layout["widgets"]) or index in indices:
            raise ValueError("Unknown or duplicate widget index")
        indices.add(index)
        original = layout["widgets"][index]
        if original.get("entity_id"):
            raise ValueError("An already linked HA widget cannot be exported as missing")
        if item.get("approved") is not True:
            continue
        candidate = {**original, "name": item.get("name"), "fields": item.get("fields")}
        checked = validate_layout({**layout, "widgets": [candidate]})["widgets"][0]
        approved.append(checked)
    generated = generate({**layout, "widgets": approved})
    generated.update({"format": "nm-studio-reviewed-ha-knx-draft", "reviewed": True,
                      "approved_count": len(approved), "selection_count": len(selection),
                      "applied": False, "source_fingerprint": fingerprint(layout)})
    return generated
