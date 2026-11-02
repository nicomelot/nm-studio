"""Read-only comparison of reviewed ETS functions with actual KNX Panel GA usage.

The panel index is authoritative only for the group-address/entity links it
returns. This does not prove an actuator's behaviour on the physical bus.
"""

try:
    from .dashboard_publisher import HAWebSocket
except ImportError:
    from dashboard_publisher import HAWebSocket


def _normalise_links(records):
    """Official KNX API returns GroupAddressEntity records, not entity_id strings."""
    if not isinstance(records, list):
        return None
    parsed = []
    for record in records:
        if isinstance(record, str):  # tolerate earlier integrations and test doubles
            parsed.append({"entity_id": record, "platform": record.partition(".")[0], "ui": None,
                           "disabled": None})
        elif isinstance(record, dict) and isinstance(record.get("unique_id"), str) and isinstance(record.get("platform"), str):
            parsed.append({"entity_id": None, "platform": record["platform"],
                           "unique_id": record["unique_id"], "ui": record.get("ui"),
                           "disabled": record.get("disabled")})
        else:
            return None
    return parsed


def audit(layout, connection_factory=HAWebSocket):
    widgets = layout.get("widgets", [])
    with connection_factory() as ws:
        groups = ws.call("knx/get_entities_by_group")
        try:
            registry = ws.call("config/entity_registry/list")
        except Exception:
            registry = []  # Missing registry permission must never imply absent entities.
    if not isinstance(groups, dict):
        raise ValueError("Indice KNX non disponibile o in formato sconosciuto")
    ids = {}
    if isinstance(registry, list):
        for item in registry:
            if (isinstance(item, dict) and item.get("platform") == "knx"
                    and isinstance(item.get("domain"), str)
                    and isinstance(item.get("unique_id"), str)
                    and isinstance(item.get("entity_id"), str)):
                key = (item["domain"], item["unique_id"])
                if key in ids and ids[key] != item["entity_id"]:
                    ids[key] = None
                else:
                    ids[key] = item["entity_id"]

    def resolve(records):
        if records is None:
            return None
        return [{**entry, "entity_id": entry.get("entity_id") or ids.get((entry["platform"], entry.get("unique_id")))}
                for entry in records]

    rows = []
    for index, widget in enumerate(widgets):
        fields = widget.get("fields") or {}
        command, feedback = fields.get("command", ""), fields.get("feedback", "")
        current = widget.get("entity_id", "")
        command_links = resolve(_normalise_links(groups.get(command, []) if command else []))
        feedback_links = resolve(_normalise_links(groups.get(feedback, []) if feedback else []))
        command_ids = {e["entity_id"] for e in command_links or [] if e.get("entity_id")}
        feedback_ids = {e["entity_id"] for e in feedback_links or [] if e.get("entity_id")}

        if not command:
            status, reason = "da_verificare", "Manca il GA di comando nella funzione ETS"
        elif command_links is None or feedback_links is None:
            status, reason = "da_verificare", "Il pannello KNX ha restituito collegamenti non interpretabili"
        elif current and current in command_ids:
            status, reason = "coerente", "Entità collegata al GA di comando nel pannello KNX"
        elif current and current in feedback_ids and current not in command_ids:
            status, reason = "sospetto", "Entità collegata soltanto al GA di feedback"
        elif command_links:
            status, reason = "ga_in_uso", "Il GA di comando è già usato da KNX; l'indice non prova a quale entity_id corrisponda"
        elif current:
            status, reason = "da_verificare", "Entità associata, ma non trovata nell'indice per il GA di comando"
        else:
            status, reason = "da_creare", "Nessuna entità KNX rilevata sul GA di comando"

        rows.append({"index": index, "name": widget.get("name", ""), "room": widget.get("room", ""),
                     "type": widget.get("type", ""), "command": command, "feedback": feedback,
                     "current_entity_id": current, "command_entities": command_links,
                     "feedback_entities": feedback_links, "status": status, "reason": reason})

    return {"read_only": True, "rows": rows, "total": len(rows),
            "counts": {status: sum(row["status"] == status for row in rows)
                       for status in ("coerente", "sospetto", "ga_in_uso", "da_verificare", "da_creare")},
            "limitations": "L'indice KNX usa identificatori interni. La riconciliazione con entity_id richiede il registro HA accessibile; non verifica DPT né comportamento del bus."}
