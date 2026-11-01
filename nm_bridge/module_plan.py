"""Installer-only module checklist. No device control or HA configuration writes."""

import json
import os
import tempfile
from pathlib import Path


PATH = Path(os.getenv("NM_MODULE_PLAN_PATH", "/data/nm_module_plan.json"))
MODULES = {
    "knx": ("ETS .knxproj disponibile", "Funzioni ETS oppure associazioni manuali", "GA comando e feedback verificati", "Interfaccia KNX/IP verificata"),
    "solar": ("Marca e modello inverter", "Integrazione HA configurata", "Produzione FV e misura scambio rete", "Accumulo e SOC, se presenti"),
    "climate": ("Tipo di generatore termico", "Marca e modello sistema", "Integrazione HA configurata", "Stati/modalità e temperature disponibili"),
}


def empty_plan():
    return {"version": 1, "modules": {key: {"enabled": False, "checked": [], "notes": ""} for key in MODULES}}


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
        clean["modules"][key] = {"enabled": info["enabled"], "checked": sorted(set(checked)), "notes": notes.strip()}
    return clean


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
