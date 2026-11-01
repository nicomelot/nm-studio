"""Build a native Home Assistant Picture Elements dashboard from saved plans.

The image is embedded as a data URL for a self-contained draft. No HA writes
or KNX bus calls occur here; only present entities receive active controls.
"""

import hashlib
import json


ICON = {
    "bulb": "mdi:lightbulb", "spot": "mdi:spotlight", "downlight": "mdi:ceiling-light",
    "led-strip": "mdi:led-strip-variant", "pendant": "mdi:ceiling-light",
    "wall": "mdi:wall-sconce-flat", "switch": "mdi:light-switch",
    "cover": "mdi:window-shutter", "thermostat": "mdi:thermostat",
    "sensor": "mdi:eye", "outlet": "mdi:power-socket-eu", "wifi": "mdi:wifi",
    "camera": "mdi:cctv", "rack": "mdi:server", "label": "mdi:map-marker",
}


def generate(archive, entities):
    existing = {e.get("entity_id") for e in entities if isinstance(e, dict)}
    views, warnings, active_count = [], [], 0
    for plan in archive.get("plans", []):
        if not plan.get("background"):
            warnings.append({"plan": plan["name"], "reason": "Sfondo non caricato"})
            continue
        elements = []
        for point in plan.get("points", []):
            ident = point.get("entity_id", "")
            if ident not in existing:
                warnings.append({"plan": plan["name"], "point": point["label"],
                                 "reason": "Entità non associata o assente in HA"})
                continue
            domain = ident.split(".", 1)[0]
            # Opening more-info lets HA provide the appropriate native
            # controls (brightness, cover actions, climate presets, etc.).
            # Toggle is enabled only for domains with a clear binary action.
            action = "toggle" if domain in {"light", "switch"} else "more-info"
            elements.append({"type": "state-icon", "entity": ident,
                             "title": point["label"], "icon": ICON.get(point.get("icon"), "mdi:map-marker"),
                             "style": {"left": str(point["x"]) + "%", "top": str(point["y"]) + "%"},
                             "tap_action": {"action": action},
                             "hold_action": {"action": "more-info"}})
            active_count += 1
        if elements:
            views.append({"title": plan["name"], "path": "mappa-" + plan["id"].replace("_", "-").lower(),
                          "cards": [{"type": "picture-elements", "image": plan["background"],
                                     "elements": elements}]})
    dashboard = {"title": "NM Studio · Planimetrie", "views": views}
    fingerprint = hashlib.sha256(json.dumps(dashboard, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return {"version": 1, "dashboard": dashboard, "fingerprint": fingerprint,
            "summary": {"views": len(views), "interactive_points": active_count,
                        "warnings": len(warnings)}, "warnings": warnings,
            "applied": False, "image_mode": "embedded_data_url"}
