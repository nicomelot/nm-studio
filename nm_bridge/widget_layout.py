"""Persist reviewed KNX dashboard templates, never bus control configuration."""

import json
import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from functools import wraps

LAYOUT_LOCK = RLock()


def locked(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with LAYOUT_LOCK:
            return function(*args, **kwargs)
    return wrapped


WIDGET_PATH = Path(os.getenv("NM_WIDGET_LAYOUT_PATH", "/data/nm_knx_widget_layout.json"))
PROJECT = re.compile(r"^[0-9a-f]{64}$")
ADDRESS = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
FIELDS = {
    "button": {"command"},
    "switch": {"command", "feedback"},
    "light": {"command", "feedback"},
    "dimmer": {"command", "feedback", "relative", "brightness", "brightness_feedback"},
    "cover": {"command", "stop", "position", "feedback", "position_command", "position_feedback"},
    "climate": {"command", "temperature", "target_temperature_state", "heat_cool", "heat_cool_state",
                "operation_mode", "operation_mode_state"},
}
HA_ENTITY = re.compile(r"^(?:light|switch|button|cover|sensor|binary_sensor|climate)\.[a-z0-9_]{1,240}$")
MAX_WIDGETS = 200
MAX_ROOMS = 200
MAX_NODES = 250


def validate_structure(nodes):
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise ValueError("Invalid building structure")
    clean = []
    by_id = {}
    sibling_names = set()
    types = {"building", "floor", "room"}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Invalid building node")
        ident, parent, kind = node.get("id"), node.get("parent"), node.get("type")
        name, active, source = node.get("name"), node.get("active", True), node.get("source", "manual")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", ident) or ident in by_id:
            raise ValueError("Invalid or duplicate building ID")
        if kind not in types or not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Invalid building node name or type")
        if not isinstance(active, bool) or source not in ("ets", "manual"):
            raise ValueError("Invalid building node flags")
        if parent is not None and (not isinstance(parent, str) or parent not in by_id):
            raise ValueError("Building parent must precede its children")
        if kind == "building" and parent is not None:
            raise ValueError("A building cannot have a parent")
        if kind != "building" and parent is None:
            raise ValueError("A floor or room requires a parent")
        if parent is not None and by_id[parent]["type"] not in ({"building"} if kind == "floor" else {"building", "floor"}):
            raise ValueError("Invalid building hierarchy")
        sibling = (parent, name.strip().casefold())
        if sibling in sibling_names:
            raise ValueError("Duplicate building node name")
        sibling_names.add(sibling)
        normalized = {"id": ident, "parent": parent, "type": kind, "name": name.strip(),
                      "active": active, "source": source}
        clean.append(normalized)
        by_id[ident] = normalized
    return clean


def validate(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1 or not PROJECT.fullmatch(str(payload.get("project", ""))):
        raise ValueError("Invalid widget layout or project")
    widgets = payload.get("widgets")
    if not isinstance(widgets, list) or len(widgets) > MAX_WIDGETS:
        raise ValueError("Invalid widget list")
    rooms = payload.get("rooms", [])
    if not isinstance(rooms, list) or len(rooms) > MAX_ROOMS or any(
            not isinstance(room, str) or not 1 <= len(room.strip()) <= 240 for room in rooms):
        raise ValueError("Invalid KNX room list")
    rooms = list(dict.fromkeys(room.strip() for room in rooms))
    structure = validate_structure(payload.get("structure", []))
    clean = []
    for item in widgets:
        if not isinstance(item, dict) or item.get("type") not in FIELDS:
            raise ValueError("Invalid widget type")
        name, room, fields = item.get("name"), item.get("room", "Da assegnare"), item.get("fields")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Invalid widget name")
        if not isinstance(room, str) or not 1 <= len(room.strip()) <= 240:
            raise ValueError("Invalid widget room")
        if not isinstance(fields, dict) or set(fields) - FIELDS[item["type"]]:
            raise ValueError("Invalid widget fields")
        if not isinstance(item.get('visible', True), bool):
            raise ValueError('Invalid dashboard visibility')
        modes = {'light': ('toggle', 'off_only'), 'button': ('on_only', 'off_only')}
        allowed = modes.get(item['type'], ('toggle',))
        mode = item.get('command_mode', allowed[0])
        if mode not in allowed:
            raise ValueError('Invalid command mode')
        if mode == 'off_only' and fields.get('feedback'):
            raise ValueError('Un pulsante solo spegnimento non usa un feedback ON/OFF')
        entity_id = item.get("entity_id", "")
        if not isinstance(entity_id, str) or (entity_id and not HA_ENTITY.fullmatch(entity_id)):
            raise ValueError("Invalid Home Assistant entity link")
        if entity_id and item["type"] in ("button", "switch") and entity_id.split(".", 1)[0] != item["type"]:
            raise ValueError("Entità Home Assistant incompatibile con il tipo di comando")
        checked = {}
        for key in FIELDS[item["type"]]:
            value = fields.get(key, "")
            if not isinstance(value, str) or (value and not ADDRESS.fullmatch(value)):
                raise ValueError("Invalid widget group address")
            checked[key] = value
        clean.append({"type": item["type"], "name": name.strip(), "room": room.strip(), "fields": checked,
                      "entity_id": entity_id, **({'command_mode': mode} if mode != 'toggle' else {}),
                      **({'visible': False} if item.get('visible') is False else {})})
    aliases = payload.get('room_aliases', {})
    if not isinstance(aliases, dict) or len(aliases) > 1500:
        raise ValueError('Invalid room aliases')
    paths = set()
    by_id = {node['id']: node for node in structure}
    for node in structure:
        parts, current = [], node
        while current:
            parts.insert(0, current['name'])
            current = by_id.get(current['parent'])
        paths.add(' / '.join(parts))
    for old, new in aliases.items():
        if not isinstance(old, str) or not 1 <= len(old) <= 240 or not isinstance(new, str) or new not in paths:
            raise ValueError('Invalid room alias path')
    return {"version": 1, "project": payload["project"], "rooms": rooms,
            "structure": structure, "widgets": clean, **({"room_aliases": aliases} if aliases else {})}


@locked
def read_layout():
    if not WIDGET_PATH.exists():
        return {"version": 1, "project": "", "rooms": [], "structure": [], "widgets": []}
    return validate(json.loads(WIDGET_PATH.read_text(encoding="utf-8")))


@locked
def save_layout(payload):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise ValueError("Explicit save confirmation required")
    clean = validate(payload)
    WIDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=WIDGET_PATH.parent, delete=False) as file:
            temp = Path(file.name)
            json.dump(clean, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, WIDGET_PATH)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"saved": len(clean["widgets"])}

