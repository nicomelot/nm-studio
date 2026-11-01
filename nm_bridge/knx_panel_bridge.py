"""Read-only capability probe for Home Assistant's official KNX WebSocket API."""

try:
    from .dashboard_publisher import HAWebSocket
except ImportError:
    from dashboard_publisher import HAWebSocket


def inspect(connection_factory=HAWebSocket):
    """Only KNX read methods; never create entities, telegrams, or modify config."""
    try:
        with connection_factory() as ws:
            base = ws.call("knx/get_base_data")
            groups = ws.call("knx/get_entities_by_group")
        if not isinstance(base, dict) or not isinstance(groups, (list, dict)):
            raise ValueError("Unexpected KNX panel response")
        connection = base.get("connection_info") or {}
        return {"available": True, "panel_access": True,
                "connected": bool(connection.get("connected")),
                "supported_platforms": base.get("supported_platforms", []),
                "group_address_entry_count": len(groups),
                "message": "KNX Panel accessibile in sola lettura. Nessuna entità creata.",
                "read_only": True}
    except Exception as exc:  # WebSocket library raises its own connection exceptions.
        # User-facing reason may include HA specifics; never log secrets or tokens.
        detail = str(exc).lower()
        if "unauthorized" in detail or "admin" in detail or "permission" in detail:
            reason = "Operazione riservata all'amministratore Home Assistant. Add-on mantenuto con permessi limitati."
        elif "not loaded" in detail or "not found" in detail or "unknown command" in detail:
            reason = "Integrazione KNX non disponibile in questa istanza Home Assistant."
        else:
            reason = "KNX Panel non interrogabile con le autorizzazioni attuali o non disponibile."
        return {"available": False, "panel_access": False, "connected": False,
                "supported_platforms": [], "group_address_entry_count": 0,
                "message": reason, "read_only": True}
