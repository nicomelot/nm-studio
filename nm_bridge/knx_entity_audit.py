"""Read-only comparison of reviewed ETS functions with actual KNX Panel GA usage.

The panel index is authoritative only for the group-address/entity links it
returns. This does not prove an actuator's behaviour on the physical bus.
"""

try:
    from .dashboard_publisher import HAWebSocket
except ImportError:
    from dashboard_publisher import HAWebSocket


def audit(layout, connection_factory=HAWebSocket):
    widgets = layout.get("widgets", [])
    with connection_factory() as ws:
        groups = ws.call("knx/get_entities_by_group")
    if not isinstance(groups, dict):
        raise ValueError("Indice KNX non disponibile o in formato sconosciuto")

    rows = []
    for index, widget in enumerate(widgets):
        fields = widget.get("fields") or {}
        command, feedback = fields.get("command", ""), fields.get("feedback", "")
        current = widget.get("entity_id", "")
        command_links = groups.get(command, []) if command else []
        feedback_links = groups.get(feedback, []) if feedback else []
        if not isinstance(command_links, list) or not all(isinstance(x, str) for x in command_links):
            command_links = None
        if not isinstance(feedback_links, list) or not all(isinstance(x, str) for x in feedback_links):
            feedback_links = None

        if not command:
            status, reason = "da_verificare", "Manca il GA di comando nella funzione ETS"
        elif command_links is None or feedback_links is None:
            status, reason = "da_verificare", "Il pannello KNX ha restituito collegamenti non interpretabili"
        elif current and current in command_links:
            status, reason = "coerente", "Entità collegata al GA di comando nel pannello KNX"
        elif current and current in feedback_links and current not in command_links:
            status, reason = "sospetto", "Entità collegata soltanto al GA di feedback"
        elif command_links:
            status, reason = "sospetto" if current else "da_associare", "Il GA di comando è già usato da altre entità KNX"
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
                       for status in ("coerente", "sospetto", "da_verificare", "da_associare", "da_creare")},
            "limitations": "I collegamenti GA↔entità provenienti dal pannello KNX non verificano DPT, stato o comportamento reale del bus."}
