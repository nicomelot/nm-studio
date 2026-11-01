"""NM Link prototype: validated, inert KNX ↔ HA mapping drafts.

No runtime engine, bus access, HA service calls or automation activation.
"""

import json
import os
import re
import tempfile
from pathlib import Path

try:
    from .widget_layout import ADDRESS
    from .dpt_registry import DPTS, LEGACY_DPT, definition, parse_sample
    from .function_engine import FUNCTIONS, interpret
except ImportError:
    from widget_layout import ADDRESS
    from dpt_registry import DPTS, LEGACY_DPT, definition, parse_sample
    from function_engine import FUNCTIONS, interpret


LINK_PATH = Path(os.getenv("NM_LINK_PATH", "/data/nm_link_drafts.json"))
ENTITY = re.compile(r"^(?:light|switch|cover|scene|sensor|binary_sensor|climate)\.[a-z0-9_]{1,240}$")
IDENTIFIER = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")
DIRECT = {"knx_to_ha", "ha_to_knx"}
MAX_LINKS = 200


def validate(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Invalid NM Link document version")
    links = payload.get("links")
    if not isinstance(links, list) or len(links) > MAX_LINKS:
        raise ValueError("Invalid NM Link list")
    clean = []
    ids = set()
    for item in links:
        if not isinstance(item, dict):
            raise ValueError("Invalid NM Link entry")
        ident = item.get("id")
        name = item.get("name")
        direction = item.get("direction")
        entity_id = item.get("entity_id")
        ga = item.get("ga")
        value_type = item.get("value_type")
        dpt = item.get("dpt") or LEGACY_DPT.get(value_type)
        function = item.get("function", "auto")
        scene_number = item.get("scene_number")
        if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident) or ident in ids:
            raise ValueError("Invalid or duplicate NM Link ID")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Invalid NM Link name")
        if direction not in DIRECT or dpt not in DPTS:
            raise ValueError("Invalid NM Link direction or value type")
        if not isinstance(entity_id, str) or (entity_id and not ENTITY.fullmatch(entity_id)):
            raise ValueError("Invalid Home Assistant entity")
        if not isinstance(ga, str) or not ADDRESS.fullmatch(ga):
            raise ValueError("Invalid KNX group address")
        if item.get("enabled", False) is not False:
            raise ValueError("Live link activation is not supported")
        if function not in FUNCTIONS:
            raise ValueError("Unsupported KNX function")
        if direction != "knx_to_ha" and function != "auto":
            raise ValueError("HA to KNX functions require a separate outbound mapping")
        requirements = {"switch": ("1.001", {"light", "switch"}),
                        "dimmer_relative": ("3.007", {"light"}),
                        "cover_move": ("1.008", {"cover"}),
                        "scene_activate": ("17.001", {"scene"})}
        if function in requirements:
            required_dpt, domains = requirements[function]
            if dpt != required_dpt or (entity_id and entity_id.split(".", 1)[0] not in domains):
                raise ValueError("Selected function is incompatible with DPT or HA domain")
        if function == "scene_activate":
            if type(scene_number) is not int or not 0 <= scene_number <= 63:
                raise ValueError("Scene mapping requires an explicit scene number 0..63")
        elif scene_number is not None:
            scene_number = None
        if direction == "knx_to_ha" and entity_id and entity_id.split(".", 1)[0] in ("light", "switch") and definition(dpt)["kind"] != "boolean":
            if function != "dimmer_relative":
                raise ValueError("Light/switch targets require a boolean or relative-dimming function")
        ids.add(ident)
        clean.append({"id": ident, "name": name.strip(), "direction": direction,
                      "ga": ga, "entity_id": entity_id, "value_type": value_type,
                      "dpt": dpt, "function": function, "scene_number": scene_number, "enabled": False})
    return {"version": 1, "links": clean}


def analyze(payload, known_entities=None):
    """No I/O. Diagnostics do not grant permission to operate the plant."""
    data = validate(payload)
    issues = []
    signatures = {}
    by_ga = {}
    for link in data["links"]:
        sig = (link["direction"], link["ga"], link["entity_id"])
        if sig in signatures:
            issues.append({"id": link["id"], "level": "warning", "code": "duplicate_link",
                           "message": "Collegamento duplicato con " + signatures[sig]})
        signatures[sig] = link["name"]
        by_ga.setdefault(link["ga"], []).append(link)
        if not link["entity_id"]:
            issues.append({"id": link["id"], "level": "warning", "code": "missing_ha_target",
                           "message": "Entità Home Assistant ancora da assegnare: collegamento incompleto"})
        elif known_entities is not None and link["entity_id"] not in known_entities:
            issues.append({"id": link["id"], "level": "warning", "code": "entity_not_found",
                           "message": "Entità non trovata nell'inventario HA corrente"})
        issues.append({"id": link["id"], "level": "info", "code": "dpt_unverified",
                       "message": "DPT selezionato " + link["dpt"] + ": verificare GA e ruolo in ETS"})
    for ga, group in by_ga.items():
        if {x["direction"] for x in group} == DIRECT:
            for link in group:
                issues.append({"id": link["id"], "level": "warning", "code": "loop_risk",
                               "message": "Stesso GA " + ga + " usato in entrambe le direzioni: possibile loop"})
        writers = [x for x in group if x["direction"] == "ha_to_knx"]
        if len({x["entity_id"] for x in writers}) > 1:
            for link in writers:
                issues.append({"id": link["id"], "level": "warning", "code": "multiple_writers",
                               "message": "Più entità HA previste come mittenti dello stesso GA " + ga})
    return {"version": 1, "read_only": True, "simulation_only": True,
            "links": data["links"], "issues": issues,
            "summary": {"total": len(data["links"]),
                        "knx_to_ha": sum(x["direction"] == "knx_to_ha" for x in data["links"]),
                        "ha_to_knx": sum(x["direction"] == "ha_to_knx" for x in data["links"]),
                        "warnings": sum(x["level"] == "warning" for x in issues)}}


def simulate(payload):
    """Explain one hypothetical event without ever triggering an action."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid NM Link simulation request")
    document = {"version": payload.get("version"), "links": payload.get("links")}
    report = analyze(document)
    selected = payload.get("link_id")
    link = next((item for item in report["links"] if item["id"] == selected), None)
    if link is None:
        raise ValueError("Select an existing NM Link draft")
    virtual = payload.get("virtual_target", False)
    if type(virtual) is not bool:
        raise ValueError("Invalid virtual device option")
    blockers = {"loop_risk", "multiple_writers", "duplicate_link", "missing_ha_target"}
    if virtual:
        blockers.remove("missing_ha_target")
    problems = [item for item in report["issues"] if item["id"] == selected and item["code"] in blockers]
    if any(other["id"] != selected and (other["direction"], other["ga"], other["entity_id"]) ==
           (link["direction"], link["ga"], link["entity_id"]) for other in report["links"]):
        problems.append({"message": "Collegamento duplicato: verificare entrambe le bozze"})
    if problems:
        return {"simulation_only": True, "executed": False, "blocked": True,
                "link_id": selected, "reasons": [item["message"] for item in problems]}
    value = parse_sample(link["dpt"], payload.get("sample"))
    kind = definition(link["dpt"])["kind"]
    effective = dict(link)
    if virtual:
        function = link.get("function", "auto")
        domain = {"switch": "light", "dimmer_relative": "light", "cover_move": "cover",
                  "scene_activate": "scene"}.get(function)
        if domain is None:
            domain = "light" if link["direction"] == "knx_to_ha" and link["dpt"] == "1.001" else "sensor"
        effective["entity_id"] = domain + ".nm_virtual_" + selected.lower().replace("-", "_")
    if link["direction"] == "knx_to_ha":
        outcome = interpret(effective, value, kind)
    else:
        outcome = {"target": "knx", "ga": link["ga"], "dpt": link["dpt"], "value": value}
    return {"simulation_only": True, "executed": False, "blocked": False,
            "virtual_target": virtual, "virtual_entity_id": effective["entity_id"] if virtual else None,
            "link_id": selected, "input": {"value_type": kind, "dpt": link["dpt"], "value": value},
            "hypothetical_effect": outcome,
            "note": "Hypothetical result only: ETS DPT and device behavior not yet verified"}


def read_links():
    if not LINK_PATH.exists():
        return {"version": 1, "links": []}
    if LINK_PATH.stat().st_size > 256 * 1024:
        raise ValueError("NM Link data is too large")
    return validate(json.loads(LINK_PATH.read_text(encoding="utf-8")))


def save_links(payload):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise ValueError("Explicit save confirmation required")
    clean = validate(payload)
    LINK_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=LINK_PATH.parent, delete=False) as handle:
            temp = Path(handle.name)
            json.dump(clean, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, LINK_PATH)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"saved": len(clean["links"]), "simulation_only": True}
