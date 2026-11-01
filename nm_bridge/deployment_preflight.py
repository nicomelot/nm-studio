"""Read-only release preflight for an installer-reviewed KNX YAML draft.

HA's state API is not an authoritative inventory of all KNX group addresses.
No Home Assistant configuration file is read, patched, or activated here.
"""

import re

try:
    from .missing_ha_generator import review
except ImportError:
    from missing_ha_generator import review


def _normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def preflight(layout, request, inventory):
    generated = review(layout, request)
    if not generated["approved_count"]:
        raise ValueError("Approve at least one device to inspect deployment")
    chosen = {item["index"]: item for item in request["devices"] if item.get("approved") is True}
    checked = []
    for index, item in chosen.items():
        widget = layout["widgets"][index]
        checked.append({"index": index, "name": item["name"].strip(), "type": widget["type"],
                        "fields": item["fields"]})

    findings = []
    by_command = {}
    by_name = {}
    for item in checked:
        idx = item["index"]
        command = item["fields"].get("command", "")
        if not command:
            findings.append({"severity": "block", "index": idx, "name": item["name"],
                             "code": "missing_command", "message": "GA comando mancante"})
        elif command in by_command:
            findings.append({"severity": "block", "index": idx, "name": item["name"],
                             "code": "duplicate_command", "message": "GA comando condiviso con " + by_command[command]})
        else:
            by_command[command] = item["name"]
        key = (_normalize(item["name"]), "cover" if item["type"] == "cover" else "light")
        if key in by_name:
            findings.append({"severity": "review", "index": idx, "name": item["name"],
                             "code": "duplicate_name", "message": "Nome simile al dispositivo " + by_name[key]})
        else:
            by_name[key] = item["name"]

        expected_domains = {"cover"} if item["type"] == "cover" else {"light", "switch"}
        similarities = [entry.get("entity_id", "") for entry in inventory
                        if entry.get("entity_id", "").split(".", 1)[0] in expected_domains
                        and _normalize(entry.get("name") or entry.get("entity_id", "").split(".")[-1]) == key[0]]
        if similarities:
            findings.append({"severity": "review", "index": idx, "name": item["name"],
                             "code": "similar_ha_entity", "message": "Entità HA con nome simile: " + ", ".join(similarities[:3])})

    # Also look at command GA already assigned to a different saved widget.
    selected_indices = set(chosen)
    for index, widget in enumerate(layout["widgets"]):
        if index in selected_indices:
            continue
        other_ga = widget.get("fields", {}).get("command", "")
        if other_ga and other_ga in by_command:
            findings.append({"severity": "review", "index": index, "name": widget.get("name", ""),
                             "code": "saved_command_overlap", "message": "GA " + other_ga +
                             " già usato da un altro widget salvato"})

    findings.append({"severity": "review", "index": None, "name": "Configurazione KNX HA",
                     "code": "unverifiable_existing_ga", "message": "Non possiamo escludere GA duplicati nella configurazione KNX HA corrente usando solo gli stati. Verifica manuale obbligatoria."})
    status = "blocked" if any(f["severity"] == "block" for f in findings) else "review_required"
    return {"format": "nm-studio-knx-deployment-preflight", "version": 1, "status": status,
            "applied": False, "approved_devices": generated["approved_count"],
            "inventory_count": len(inventory), "source_fingerprint": generated["source_fingerprint"],
            "findings": findings, "yaml": generated["yaml"],
            "checklist": [
                "Esegui un backup completo di Home Assistant prima di intervenire.",
                "Esporta e conserva la configurazione KNX attuale e la lista delle entità esistenti.",
                "Confronta manualmente tutti i GA e i DPT della bozza con ETS e con la configurazione KNX già attiva.",
                "Verifica i nomi delle entità per evitare duplicati e rinumerazioni.",
                "Integra la bozza nella chiave knx esistente, senza crearne una seconda.",
                "Valida la configurazione Home Assistant prima di riavviare; applica soltanto in una finestra di manutenzione.",
                "In caso di errore ripristina il backup e la configurazione KNX precedente; controlla gli stati e i comandi.",
            ],
            "limitations": "Preparazione soltanto: non applica YAML, non crea entità, non riavvia HA e non invia telegrammi KNX."}
