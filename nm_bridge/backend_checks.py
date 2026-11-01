"""Read-only configuration diagnostics and portable, bounded backups.

No KNX transport, Home Assistant service calls or configuration writes.
"""

import json
from datetime import datetime, timezone
try:
    from .nm_link import LINK_PATH
except ImportError:
    from nm_link import LINK_PATH

try:
    from .audit_notes import NOTES_PATH
    from .knx_devices import DEVICE_PATH, read_devices
    from .widget_layout import WIDGET_PATH, read_layout as read_widgets
except ImportError:  # Docker runs bridge.py from /app as a script.
    from audit_notes import NOTES_PATH
    from knx_devices import DEVICE_PATH, read_devices
    from widget_layout import WIDGET_PATH, read_layout as read_widgets


MAX_FILE_BYTES = 1024 * 1024


def inspect_configuration(widget_data=None, approved=None, ha_entity_ids=None):
    """Return actionable warnings; never infer a KNX DPT from a GA name."""
    widget_data = read_widgets() if widget_data is None else widget_data
    approved = read_devices() if approved is None else approved
    widgets = widget_data["widgets"]
    issues = []
    command_owners = {}
    for index, widget in enumerate(widgets):
        kind, fields = widget["type"], widget["fields"]
        name = widget["name"]

        def issue(code, severity, field, detail):
            issues.append({"index": index, "widget": name, "code": code,
                           "severity": severity, "field": field, "detail": detail})

        if not fields.get("command"):
            issue("missing_command", "blocking", "command", "Indirizzo comando mancante")
        else:
            command_owners.setdefault(fields["command"], []).append(index)
        if not fields.get("feedback"):
            issue("missing_feedback", "warning", "feedback", "Stato non disponibile: associare un GA verificato")
        if kind == "cover" and not fields.get("stop"):
            issue("missing_stop", "warning", "stop", "Indirizzo stop non configurato")
        if kind == "dimmer" and not fields.get("brightness"):
            issue("missing_brightness", "warning", "brightness", "Indirizzo regolazione assoluta non configurato")
        if kind == "cover" and fields.get("position"):
            issue("position_unverified", "warning", "position", "Verificare DPT e ruolo del GA di posizione in ETS")
        if kind == "cover" and fields.get("feedback"):
            issue("cover_feedback_unverified", "warning", "feedback", "Il feedback generico non certifica una posizione percentuale")
        if not widget.get("entity_id"):
            issue("missing_ha_link", "info", "entity_id", "Nessuna entità Home Assistant collegata")
        elif ha_entity_ids is not None and widget["entity_id"] not in ha_entity_ids:
            issue("unknown_ha_entity", "warning", "entity_id", "Entità Home Assistant non trovata")
        if widget.get("room") == "Da assegnare":
            issue("unassigned_room", "info", "room", "Ambiente da assegnare")
    for address, indices in command_owners.items():
        if len(indices) > 1:
            for index in indices:
                issues.append({"index": index, "widget": widgets[index]["name"],
                               "code": "duplicate_command", "severity": "warning",
                               "field": "command", "detail": "GA comando condiviso: " + address})
    return {"read_only": True, "project": widget_data["project"],
            "widgets": len(widgets), "approved_devices": len(approved),
            "issues": issues,
            "totals": {level: sum(i["severity"] == level for i in issues)
                       for level in ("blocking", "warning", "info")},
            "ha_entity_check": "performed" if ha_entity_ids is not None else "not_performed",
            "ready_for_automatic_activation": False}


def export_backup(layout_path):
    """Snapshot only NM Studio settings, with no tokens or imported ETS archive."""
    files = {"ha_layout": layout_path, "knx_widgets": WIDGET_PATH,
             "approved_devices": DEVICE_PATH, "review_notes": NOTES_PATH,
             "nm_link_drafts": LINK_PATH}
    snapshot = {}
    for key, path in files.items():
        if not path.exists():
            snapshot[key] = None
            continue
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Backup data exceeds the per-file size limit")
        snapshot[key] = json.loads(path.read_text(encoding="utf-8"))
    return {"format": "nm-studio-backup", "version": 1, "read_only": True,
            "created_at": datetime.now(timezone.utc).isoformat(), "data": snapshot,
            "restore_supported": False}
