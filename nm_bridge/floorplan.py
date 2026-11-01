"""Installer's floorplan annotations, independent of Home Assistant and KNX bus."""

import base64
import json
import os
import re
import tempfile
from pathlib import Path


PATH = Path(os.getenv("NM_FLOORPLAN_PATH", "/data/nm_floorplans.json"))
ID = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")
KINDS = {"light", "dali", "knx", "data", "wifi", "camera", "climate", "rack"}
ICONS = {"bulb", "spot", "downlight", "led-strip", "pendant", "wall", "switch",
         "cover", "thermostat", "sensor", "outlet", "wifi", "camera", "rack", "label"}
ENTITY = re.compile(r"^(?:light|switch|cover|sensor|binary_sensor|climate|fan|media_player)\.[a-z0-9_]{1,240}$")
MAX_IMAGE = 2 * 1024 * 1024


def empty():
    return {"version": 1, "plans": []}


def _image(data):
    if data in (None, ""):
        return None
    if not isinstance(data, str) or not data.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
        raise ValueError("Only PNG/JPEG backgrounds are accepted")
    header, encoded = data.split(",", 1)
    if len(encoded) > (MAX_IMAGE * 4 // 3 + 8):
        raise ValueError("Image exceeds 2 MB")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        raise ValueError("Invalid image encoding") from None
    if len(raw) > MAX_IMAGE:
        raise ValueError("Image exceeds 2 MB")
    if header.endswith("png;base64") and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature")
    if header.endswith("jpeg;base64") and not raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("Invalid JPEG signature")
    return data


def validate(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("plans"), list) or len(payload["plans"]) > 15:
        raise ValueError("Invalid floorplan archive")
    seen, cleaned = set(), []
    for plan in payload["plans"]:
        if not isinstance(plan, dict):
            raise ValueError("Invalid floorplan")
        pid, name = plan.get("id"), plan.get("name")
        if not isinstance(pid, str) or not ID.fullmatch(pid) or pid in seen:
            raise ValueError("Invalid or duplicate floorplan ID")
        seen.add(pid)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Invalid floorplan name")
        points = plan.get("points")
        if not isinstance(points, list) or len(points) > 300:
            raise ValueError("Invalid floorplan points")
        ids, clean_points = set(), []
        for point in points:
            if not isinstance(point, dict) or not isinstance(point.get("id"), str) or not ID.fullmatch(point["id"]) or point["id"] in ids:
                raise ValueError("Invalid point ID")
            ids.add(point["id"])
            kind, label, x, y = point.get("kind"), point.get("label"), point.get("x"), point.get("y")
            if not isinstance(kind, str) or kind not in KINDS or not isinstance(label, str) or not 1 <= len(label.strip()) <= 65:
                raise ValueError("Invalid point label or kind")
            if type(x) not in (int, float) or type(y) not in (int, float) or not 0 <= x <= 100 or not 0 <= y <= 100:
                raise ValueError("Invalid point position")
            entity_id, icon = point.get("entity_id", ""), point.get("icon", "label")
            if not isinstance(entity_id, str) or (entity_id and not ENTITY.fullmatch(entity_id)):
                raise ValueError("Invalid floorplan Home Assistant entity")
            if icon not in ICONS:
                raise ValueError("Invalid floorplan symbol")
            # Multiple physical points may intentionally reference the same HA entity.
            clean_points.append({"id": point["id"], "kind": kind, "label": label.strip(), "x": round(x, 3), "y": round(y, 3),
                                 "entity_id": entity_id, "icon": icon})
        cleaned.append({"id": pid, "name": name.strip(), "background": _image(plan.get("background")), "points": clean_points})
    return {"version": 1, "plans": cleaned}


def read():
    if not PATH.exists():
        return empty()
    return validate(json.loads(PATH.read_text(encoding="utf-8")))


def save(data):
    clean = validate(data)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=PATH.parent, delete=False) as file:
            temp = Path(file.name)
            json.dump(clean, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, PATH)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"saved": True, "plans": len(clean["plans"]), "points": sum(len(x["points"]) for x in clean["plans"])}
