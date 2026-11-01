"""Installer-only module checklist. No device control or HA configuration writes."""

import json
import os
import tempfile
import re
from pathlib import Path


PATH = Path(os.getenv("NM_MODULE_PLAN_PATH", "/data/nm_module_plan.json"))
MODULES = {
    "knx": ("ETS .knxproj disponibile", "Funzioni ETS oppure associazioni manuali", "GA comando e feedback verificati", "Interfaccia KNX/IP verificata"),
    "solar": ("Marca e modello inverter", "Integrazione HA configurata", "Produzione FV e misura scambio rete", "Accumulo e SOC, se presenti"),
    "climate": ("Tipo di generatore termico", "Marca e modello sistema", "Integrazione HA configurata", "Stati/modalità e temperature disponibili"),
}
ROLES = {"knx": ("control",), "solar": ("pv_power", "grid_power", "battery_soc"),
         "climate": ("room_temperature", "climate_mode")}
ENTITY = re.compile(r"^(?:sensor|binary_sensor|light|switch|cover|climate)\.[a-z0-9_]{1,120}$")


def empty_plan():
    return {"version": 1, "modules": {key: {"enabled": False, "checked": [], "notes": "", "assignments": {}, "verified": []} for key in MODULES}}


def validate(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("modules"), dict):
        raise ValueError("Invalid module plan")
    if set(payload["modules"]) != set(MODULES):
        raise ValueError("Unexpected module names")
    clean = empty_plan()
    for key, steps in MODULES.items():
        info = payload["modules"][key]
        if not isinstance(info, dict) or type(info.get("enabled")) is not bool:
            raise ValueError("Invalid module selection")
        checked, notes = info.get("checked"), info.get("notes")
        if not isinstance(checked, list) or len(checked) > len(steps) or not all(type(i) is int and 0 <= i < len(steps) for i in checked):
            raise ValueError("Invalid checklist")
        if not isinstance(notes, str) or len(notes) > 500:
            raise ValueError("Invalid installer notes")
        assigned = info.get("assignments", {})
        if not isinstance(assigned, dict) or any(role not in ROLES[key] or not isinstance(entity, str) or not ENTITY.fullmatch(entity) for role, entity in assigned.items()):
            raise ValueError("Invalid HA entity assignments")
        verified = info.get("verified", [])
        if not isinstance(verified, list) or len(verified) > len(ROLES[key]) or any(not isinstance(role, str) or role not in assigned for role in verified):
            raise ValueError("Verified roles must have an assigned entity")
        clean["modules"][key] = {"enabled": info["enabled"], "checked": sorted(set(checked)),
                                 "notes": notes.strip(), "assignments": dict(assigned), "verified": sorted(set(verified))}
    return clean


ROLE_RULES = {
    "control": (("light", "switch", "cover"), (), None),
    "pv_power": (("sensor",), ("fotovolta", "solar", "pv", "produzione"), "W"),
    "grid_power": (("sensor",), ("rete", "grid", "scambio", "import", "export"), "W"),
    "battery_soc": (("sensor",), ("batter", "battery", "soc", "carica"), "%"),
    "room_temperature": (("sensor",), ("temperatur", "temperature", "temp"), "°C"),
    "climate_mode": (("climate",), (), None),
}


def suggest_entities(entities):
    """Suggest candidates from names/domains/units only; never approve a mapping."""
    output = {module: {} for module in ROLES}
    for module, roles in ROLES.items():
        for role in roles:
            domains, keywords, unit = ROLE_RULES[role]
            candidates = []
            for item in entities[:2000] if isinstance(entities, list) else []:
                if not isinstance(item, dict):
                    continue
                entity = item.get("entity_id")
                if not isinstance(entity, str) or not ENTITY.fullmatch(entity) or entity.split(".")[0] not in domains:
                    continue
                name = str(item.get("name", ""))[:120]
                haystack = (name + " " + entity).casefold()
                if keywords and not any(term in haystack for term in keywords):
                    continue
                observed_unit = item.get("unit")
                # An absent HA unit is uncertainty, not proof of incompatibility.
                # A known incompatible unit (e.g. kWh vs W) is excluded.
                if unit is not None and observed_unit not in (None, "", unit):
                    continue
                if str(item.get("state", "")).lower() in ("unknown", "unavailable"):
                    continue
                uncertain = unit is not None and observed_unit in (None, "")
                candidates.append({"entity_id": entity, "name": name, "unit": observed_unit,
                                   "needs_unit_verification": uncertain,
                                   "evidence": "Unità non dichiarata in HA: verifica manuale obbligatoria" if uncertain else
                                   "Dominio, nome e unità compatibili" if unit else "Dominio Home Assistant compatibile"})
            candidates.sort(key=lambda item: (item["needs_unit_verification"], item["entity_id"]))
            output[module][role] = candidates[:8]
    return {"read_only": True, "automatic_approval": False, "suggestions": output,
            "entities_examined": min(len(entities), 2000) if isinstance(entities, list) else 0}


def read():
    if not PATH.exists():
        return empty_plan()
    return validate(json.loads(PATH.read_text(encoding="utf-8")))


def save(payload):
    clean = validate(payload)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=PATH.parent, delete=False) as file:
            tmp = Path(file.name)
            json.dump(clean, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, PATH)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return clean
