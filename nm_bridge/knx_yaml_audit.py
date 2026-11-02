"""Conservative, read-only audit of a KNX YAML snippet exported by an installer.

This deliberately supports only the simple `light`/`cover` lists emitted by
older importers. It never resolves YAML tags, references or includes and never
claims that an address is a confirmed physical circuit.
"""

import re

GA = re.compile(r"^\d{1,2}/\d{1,3}/\d{1,3}$")
SECTION = re.compile(r"^([a-z_]+):\s*(?:#.*)?$")
FIELD = re.compile(r"^    ([a-z_]+):\s*(.*?)\s*$")
PAIR = re.compile(r"^  - ([a-z_]+):\s*(.*?)\s*$")
ADDRESS_KEYS = {"address", "state_address", "brightness_address", "brightness_state_address",
                "move_long_address", "move_short_address", "stop_address", "position_address",
                "position_state_address", "angle_address", "angle_state_address"}


def _scalar(value):
    value = value.strip()
    if value[:1] in ("'", '"') and value[-1:] == value[:1]:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def inspect_yaml(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > 128 * 1024:
        raise ValueError("File YAML assente o superiore a 128 KB")
    section, entries, current, warnings = None, [], None, []
    for lineno, line in enumerate(source.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = SECTION.fullmatch(line)
        if match:
            section = match.group(1)
            current = None
            continue
        if section not in ("light", "cover"):
            continue
        match = PAIR.fullmatch(line)
        if match:
            current = {"type": section, "line": lineno}
            entries.append(current)
        else:
            match = FIELD.fullmatch(line)
            if not match or current is None:
                warnings.append(f"Riga {lineno}: sintassi non riconosciuta, verificare a mano")
                current = None
                continue
        key, raw = match.groups()
        if "!" in raw or "&" in raw or "*" in raw:
            raise ValueError("YAML con riferimenti o tag: analisi automatica non supportata")
        value = _scalar(raw)
        if key in ADDRESS_KEYS and value and not GA.fullmatch(value):
            warnings.append(f"Riga {lineno}: indirizzo {key} non interpretabile")
        current[key] = value

    if not entries:
        raise ValueError("Nessuna entità light/cover leggibile: carica il contenuto KNX, non configuration.yaml")

    commands = {}
    feedback = {}
    for entry in entries:
        command = entry.get("address") if entry["type"] == "light" else entry.get("move_long_address")
        if command and GA.fullmatch(command):
            commands.setdefault((entry["type"], command), []).append(entry)
        for key in ("state_address", "brightness_state_address", "position_state_address", "angle_state_address"):
            ga = entry.get(key)
            if ga and GA.fullmatch(ga):
                feedback.setdefault(ga, []).append(entry)

    groups = []
    for (kind, ga), members in sorted(commands.items()):
        groups.append({"type": kind, "command": ga, "count": len(members),
                       "names": [e.get("name", "") for e in members],
                       "lines": [e["line"] for e in members],
                       "feedback": sorted({e.get("state_address", "") for e in members if e.get("state_address")}),
                       "duplicate": len(members) > 1,
                       "note": "Stesso GA in più entità; verificare se rappresentano un unico circuito" if len(members) > 1 else "Un'entità sul GA; non prova unicità fisica"})

    standalone_feedback = []
    for entry in entries:
        if entry["type"] != "light":
            continue
        name = entry.get("name", "")
        ga = entry.get("address", "")
        if ga and re.search(r"\b(stato|notifica|feedback)\b", name, re.I):
            standalone_feedback.append({"name": name, "address": ga, "line": entry["line"],
                                        "reason": "Nome compatibile con un feedback, ma configurato come luce comandabile"})

    return {"read_only": True, "entities": len(entries),
            "counts": {"light": sum(e["type"] == "light" for e in entries),
                       "cover": sum(e["type"] == "cover" for e in entries),
                       "duplicate_groups": sum(g["duplicate"] for g in groups),
                       "extra_entities": sum(g["count"] - 1 for g in groups if g["duplicate"]),
                       "feedback_candidates": len(standalone_feedback)},
            "groups": groups, "feedback_candidates": standalone_feedback,
            "warnings": warnings[:30],
            "limitations": "Confronto sintattico di un estratto YAML: non legge include, DPT, ETS o bus. Nessun intervento sulla configurazione."}
