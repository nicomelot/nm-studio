"""Installer-reviewed KNX association records. No bus connections or commands."""

import json
import os
import re
import tempfile
from pathlib import Path

DEVICE_PATH = Path(os.getenv("NM_KNX_DEVICE_PATH", "/data/nm_knx_approved.json"))
ALLOWED_KINDS = {"light", "dimmer", "cover", "climate", "binary", "unknown"}
ADDRESS = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
LIMIT = 300


def validate_device(d):
    if not isinstance(d, dict):
        raise ValueError("Invalid device")
    name, kind = d.get("name"), d.get("kind")
    command, feedback = d.get("command"), d.get("feedback")
    stop, position = d.get("stop"), d.get("position")
    room = d.get("room", "Da assegnare")
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 80):
        raise ValueError("Device name is required")
    if kind not in ALLOWED_KINDS:
        raise ValueError("Invalid device kind")
    if not isinstance(command, str) or not ADDRESS.fullmatch(command):
        raise ValueError("Command address is required")
    if feedback is not None and (not isinstance(feedback, str) or not ADDRESS.fullmatch(feedback)):
        raise ValueError("Invalid feedback address")
    if command == feedback:
        raise ValueError("Command and feedback must differ")
    for extra in (stop, position):
        if extra is not None and (not isinstance(extra, str) or not ADDRESS.fullmatch(extra)):
            raise ValueError("Invalid auxiliary group address")
    if len({x for x in (command, feedback, stop, position) if x is not None}) != len([x for x in (command, feedback, stop, position) if x is not None]):
        raise ValueError("Group addresses must be distinct")
    if kind != "cover" and (stop is not None or position is not None):
        raise ValueError("Auxiliary group addresses are only supported for covers")
    if not isinstance(room, str) or not (1 <= len(room.strip()) <= 80):
        raise ValueError("Invalid room name")
    return {"name": name.strip(), "kind": kind, "command": command, "feedback": feedback, "room": room.strip(),
            "stop": stop, "position": position}


def read_devices():
    if not DEVICE_PATH.exists():
        return []
    raw = json.loads(DEVICE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) > LIMIT:
        raise ValueError("Invalid approved devices file")
    return [validate_device(d) for d in raw]


def confirm_devices(payload):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise ValueError("Explicit confirmation required")
    incoming = payload.get("devices")
    if not isinstance(incoming, list) or not 1 <= len(incoming) <= 100:
        raise ValueError("Select 1 to 100 devices")
    additions = [validate_device(d) for d in incoming]
    saved = read_devices()
    existing = {d["command"] for d in saved}
    for d in additions:
        if d["command"] in existing:
            raise ValueError("Duplicate command address: " + d["command"])
        existing.add(d["command"])
    if len(saved) + len(additions) > LIMIT:
        raise ValueError("Device limit reached")
    result = saved + additions
    DEVICE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DEVICE_PATH.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump(result, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DEVICE_PATH)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return {"saved": len(additions), "total": len(result)}
