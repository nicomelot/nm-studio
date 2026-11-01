"""Portable, integrity-checked NM Studio local-data migration.

This only reads/writes the app's five /data JSON files. No HA or KNX actions.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

try:
    from . import audit_notes, knx_devices, nm_link, widget_layout
except ImportError:
    import audit_notes
    import knx_devices
    import nm_link
    import widget_layout


FORMAT = "nm-studio-migration"
MAX_BUNDLE = 1024 * 1024
KEYS = ("rooms", "widgets", "approved", "ets_reviews", "nm_links")


def locations(ui_path):
    return {"rooms": Path(ui_path), "widgets": widget_layout.WIDGET_PATH,
            "approved": knx_devices.DEVICE_PATH, "ets_reviews": audit_notes.NOTES_PATH,
            "nm_links": nm_link.LINK_PATH}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def checksum(files):
    return hashlib.sha256(canonical(files)).hexdigest()


def export_bundle(ui_path, validate_rooms):
    files = {}
    for key, path in locations(ui_path).items():
        if not path.exists():
            files[key] = None
            continue
        if path.stat().st_size > MAX_BUNDLE:
            raise ValueError("Migration source exceeds size limit: " + key)
        files[key] = json.loads(path.read_text(encoding="utf-8"))
    validated = validate_files(files, validate_rooms)
    return {"format": FORMAT, "version": 1, "files": validated,
            "sha256": checksum(validated), "contains": [k for k, v in validated.items() if v is not None],
            "note": "Backup NM Studio locale; conservare in un luogo sicuro. Non contiene token Supervisor."}


def validate_files(files, validate_rooms):
    if not isinstance(files, dict) or set(files) != set(KEYS):
        raise ValueError("Missing or unknown migration data sections")
    clean = {}
    if files["rooms"] is not None:
        clean["rooms"] = validate_rooms(files["rooms"])
    else:
        clean["rooms"] = None
    clean["widgets"] = widget_layout.validate(files["widgets"]) if files["widgets"] is not None else None
    if files["approved"] is None:
        clean["approved"] = None
    else:
        raw = files["approved"]
        if not isinstance(raw, list) or len(raw) > knx_devices.LIMIT:
            raise ValueError("Invalid approved devices backup")
        devices = [knx_devices.validate_device(d) for d in raw]
        commands = [d["command"] for d in devices]
        if len(commands) != len(set(commands)):
            raise ValueError("Duplicate approved device commands")
        clean["approved"] = devices
    if files["ets_reviews"] is None:
        clean["ets_reviews"] = None
    else:
        reviews = files["ets_reviews"]
        if not isinstance(reviews, dict) or len(reviews) > 100:
            raise ValueError("Invalid ETS review archive")
        for project, entries in reviews.items():
            if not audit_notes.PROJECT.fullmatch(project) or not isinstance(entries, dict) or len(entries) > 6000:
                raise ValueError("Invalid ETS project review")
            for address, record in entries.items():
                if not audit_notes.ADDRESS.fullmatch(address) or not isinstance(record, dict):
                    raise ValueError("Invalid ETS review address")
                if record.get("status") not in audit_notes.STATES or not isinstance(record.get("note", ""), str) or len(record.get("note", "")) > 500:
                    raise ValueError("Invalid ETS review note")
        clean["ets_reviews"] = reviews
    clean["nm_links"] = nm_link.validate(files["nm_links"]) if files["nm_links"] is not None else None
    return clean


def restore_bundle(bundle, ui_path, validate_rooms, confirm=False, overwrite=False):
    if not confirm:
        raise ValueError("Explicit migration confirmation required")
    if not isinstance(bundle, dict) or bundle.get("format") != FORMAT or bundle.get("version") != 1:
        raise ValueError("Invalid migration format")
    files = bundle.get("files")
    if not isinstance(files, dict) or checksum(files) != bundle.get("sha256"):
        raise ValueError("Backup checksum mismatch")
    clean = validate_files(files, validate_rooms)
    paths = locations(ui_path)
    targets = {k: paths[k] for k, data in clean.items() if data is not None}
    existing = [k for k, p in targets.items() if p.exists()]
    if existing and not overwrite:
        raise ValueError("Destination contains data: " + ", ".join(existing) + ". Export its backup first.")
    if not targets:
        raise ValueError("Backup contains no data")
    originals = {k: p.read_bytes() if p.exists() else None for k, p in targets.items()}
    staged = {}
    updated = []
    try:
        for key, path in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as file:
                staged[key] = Path(file.name)
                file.write(canonical(clean[key]))
                file.flush()
                os.fsync(file.fileno())
        for key, path in targets.items():
            os.replace(staged[key], path)
            updated.append(key)
    except Exception:
        for key in reversed(updated):
            original = originals[key]
            path = targets[key]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as rollback:
                    rollback.write(original)
                    rollback.flush()
                    os.fsync(rollback.fileno())
                    rollback_path = Path(rollback.name)
                os.replace(rollback_path, path)
        raise
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)
    return {"restored": len(targets), "sections": list(targets), "overwrote": existing,
            "home_assistant_modified": False, "knx_commands_sent": False}
