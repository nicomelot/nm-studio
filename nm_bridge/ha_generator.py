"""Draft Home Assistant KNX YAML from installer-saved widget mappings.

Pure data transformation: never writes configuration, runs HA actions or
connects to a KNX interface. All generated mappings require human review.
"""

import json
import re

try:
    from .widget_layout import read_layout
except ImportError:
    from widget_layout import read_layout


GROUP_ADDRESS = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
MAX_CONNECTIONS = 12


def object_bits(size):
    """Only unambiguous ETS catalogue sizes are used as compatibility evidence."""
    normalized = re.sub(r"\s+", "", size).lower()
    if normalized in ("1bit", "1bits"):
        return 1
    if normalized in ("1byte", "1bytes", "8bit", "8bits"):
        return 8
    return None


def validate_evidence(payload, project):
    """Bound a transient ETS snapshot; it never changes persistent approvals."""
    if not isinstance(payload, dict) or payload.get("project") != project:
        raise ValueError("ETS project does not match saved KNX widgets")
    addresses = payload.get("addresses")
    if not isinstance(addresses, list) or len(addresses) > 5000:
        raise ValueError("Invalid ETS evidence list")
    evidence = {}
    for record in addresses:
        if not isinstance(record, dict) or not GROUP_ADDRESS.fullmatch(str(record.get("address", ""))):
            raise ValueError("Invalid ETS evidence address")
        dpt, linked = record.get("dpt", ""), record.get("linked")
        if not isinstance(dpt, str) or len(dpt) > 100 or not isinstance(linked, bool):
            raise ValueError("Invalid ETS evidence metadata")
        if record["address"] in evidence:
            raise ValueError("Duplicate ETS evidence address")
        connections = record.get("connections", [])
        if not isinstance(connections, list) or len(connections) > MAX_CONNECTIONS:
            raise ValueError("Invalid ETS object connections")
        clean_connections = []
        for connection in connections:
            if not isinstance(connection, dict):
                raise ValueError("Invalid ETS object connection")
            size = connection.get("size", "")
            function = connection.get("function", "")
            if not isinstance(size, str) or len(size) > 32 or not isinstance(function, str) or len(function) > 100:
                raise ValueError("Invalid ETS object details")
            clean_connections.append({"size": size, "function": function})
        evidence[record["address"]] = {"dpt": dpt, "linked": linked, "connections": clean_connections}
    return evidence


def generate(layout=None, evidence=None):
    layout = read_layout() if layout is None else layout
    entries = {"light": [], "cover": [], "climate": [], "switch": []}
    warnings = []
    seen = {}
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("Invalid ETS evidence")
    for index, widget in enumerate(layout["widgets"]):
        kind = widget["type"]
        fields = dict(widget["fields"])
        command = fields.get("command")
        name = widget["name"]
        if not command:
            warnings.append({"index": index, "name": name, "code": "missing_command",
                             "message": "Comando mancante: dispositivo escluso dall'anteprima"})
            continue
        if evidence is not None and command in evidence and not evidence[command]["linked"]:
            warnings.append({"index": index, "name": name, "code": "command_unlinked",
                             "message": "Comando non collegato nel progetto ETS: dispositivo escluso"})
            continue
        if evidence is not None:
            for field, address in list(fields.items()):
                if field != "command" and address and address in evidence and not evidence[address]["linked"]:
                    fields[field] = ""
                    warnings.append({"index": index, "name": name, "code": "field_unlinked",
                                     "message": field + ": GA " + address + " scollegato in ETS, escluso dalla bozza"})
        if kind == "button":
            warnings.append({"index": index, "name": name, "code": "button_panel_only",
                             "message": "Pulsante: usa Installazione e collaudo per creare l’entità dal pannello KNX."})
            continue
        platform = kind if kind in ("cover", "climate", "switch") else "light"
        if platform == "climate" and (not fields.get("temperature") or not fields.get("target_temperature_state")):
            warnings.append({"index": index, "name": name, "code": "climate_missing_required",
                             "message": "Termostato escluso: temperatura ambiente e feedback setpoint obbligatori per HA KNX"})
            continue
        key = (platform, command)
        if key in seen:
            warnings.append({"index": index, "name": name, "code": "duplicate_command",
                             "message": "GA comando già usato da " + seen[key] + ": dispositivo escluso"})
            continue
        seen[key] = name
        entry = {"name": name}
        if platform == "climate":
            entry["temperature_address"] = fields["temperature"]
            entry["target_temperature_address"] = command
            entry["target_temperature_state_address"] = fields["target_temperature_state"]
            for field in ("heat_cool", "heat_cool_state", "operation_mode", "operation_mode_state",
                          "on_off", "on_off_state", "controller_mode", "controller_mode_state",
                          "fan_speed", "fan_speed_state", "swing", "swing_state"):
                if fields.get(field):
                    entry[field + "_address"] = fields[field]
            warnings.append({"index": index, "name": name, "code": "check_climate_dpt",
                             "message": "Verificare setpoint e temperatura DPT 9.001, caldo/freddo DPT 1.100 e modalità DPT 20.102; modalità HVAC non presunte"})
        elif platform in ("light", "switch"):
            entry["address"] = command
            warnings.append({"index": index, "name": name, "code": "check_switch_dpt",
                             "message": "Verificare DPT 1.001 del comando in ETS"})
            if fields.get("feedback"):
                entry["state_address"] = fields["feedback"]
                warnings.append({"index": index, "name": name, "code": "check_switch_state_dpt",
                                 "message": "Verificare DPT 1.001 del feedback in ETS"})
            else:
                warnings.append({"index": index, "name": name, "code": "missing_feedback",
                                 "message": "Stato non collegato; nessun feedback inventato"})
            if kind == "dimmer":
                if fields.get("brightness"):
                    entry["brightness_address"] = fields["brightness"]
                    warnings.append({"index": index, "name": name, "code": "check_brightness_dpt",
                                     "message": "Verificare DPT 5.001 della luminosità assoluta"})
                if fields.get("brightness_feedback"):
                    entry["brightness_state_address"] = fields["brightness_feedback"]
                    warnings.append({"index": index, "name": name, "code": "check_brightness_state_dpt",
                                     "message": "Verificare DPT 5.001 del feedback luminosità"})
                if fields.get("relative"):
                    warnings.append({"index": index, "name": name, "code": "relative_unmapped",
                                     "message": "Regolazione relativa non inclusa: richiede verifica separata"})
        else:
            entry["move_long_address"] = command
            for field, target in (("position_command", "position_address"),
                                  ("position_feedback", "position_state_address")):
                if fields.get(field):
                    entry[target] = fields[field]
                    warnings.append({"index": index, "name": name, "code": "check_" + field,
                                     "message": "Verificare direzione e DPT 5.001 di " + field})
            if fields.get("stop"):
                entry["stop_address"] = fields["stop"]
                warnings.append({"index": index, "name": name, "code": "check_stop_dpt",
                                 "message": "Verificare DPT 1.001 del comando stop in ETS"})
            else:
                warnings.append({"index": index, "name": name, "code": "missing_stop",
                                 "message": "Stop non configurato"})
            if fields.get("position"):
                warnings.append({"index": index, "name": name, "code": "position_not_exported",
                                 "message": "GA posizione escluso finché collegamento e DPT 5.001 non sono verificati"})
            if fields.get("feedback"):
                warnings.append({"index": index, "name": name, "code": "cover_feedback_not_exported",
                                 "message": "Feedback generico escluso: non equivale a stato posizione DPT 5.001"})
            warnings.append({"index": index, "name": name, "code": "check_cover_dpt",
                             "message": "Verificare DPT 1 di movimento e stop e direzione Su/Giù"})
        entries[platform].append(entry)

    lines = ["# NM Control - bozza da verificare in ETS prima di applicare",
             "# Non applicata automaticamente. L'uso in HA abilita possibili comandi sul bus.",
             "# Integrare nella chiave knx: esistente, senza duplicarla.", "knx:"]
    for platform in entries:
        if not entries[platform]:
            continue
        lines.append("  " + platform + ":")
        for entry in entries[platform]:
            for pos, (field, value) in enumerate(entry.items()):
                # JSON double-quoted strings are a safe YAML scalar subset.
                prefix = "    - " if pos == 0 else "      "
                lines.append(prefix + field + ": " + json.dumps(value, ensure_ascii=True))
    if not any(entries.values()):
        lines.append("  # Nessun dispositivo con comando configurato")
    confirmed = 0
    compatible = 0
    if evidence is not None:
        expected = {"command": "1.001", "feedback": "1.001", "stop": "1.001",
                    "brightness": "5.001", "brightness_feedback": "5.001"}
        for warning in warnings:
            widget = layout["widgets"][warning["index"]]
            code = warning["code"]
            field = {"check_switch_dpt": "command", "check_switch_state_dpt": "feedback",
                     "check_brightness_dpt": "brightness", "check_brightness_state_dpt": "brightness_feedback",
                     "check_cover_dpt": "command", "check_stop_dpt": "stop"}.get(code)
            if not field:
                continue
            address = widget["fields"].get(field)
            record = evidence.get(address)
            if record is None:
                warning["message"] += " · GA non presente nei dati ETS forniti"
                continue
            if not record["linked"]:
                warning["message"] += " · GA NON COLLEGATO in ETS"
                continue
            dpt = record["dpt"].replace(" ", "").upper()
            target = expected[field]
            aliases = {"1.001": ("DPST-1-1", "DPT-1.001"),
                       "5.001": ("DPST-5-1", "DPT-5.001")}[target]
            if dpt in aliases:
                warning["verified"] = True
                warning["message"] = "DPT " + target + " dichiarato in ETS e GA collegato"
                confirmed += 1
            elif dpt:
                warning["message"] += " · ETS dichiara " + record["dpt"]
            else:
                sizes = [object_bits(obj.get("size", "")) for obj in record.get("connections", [])]
                expected_bits = 1 if target == "1.001" else 8
                known = [size for size in sizes if size is not None]
                if known and all(size == expected_bits for size in known):
                    warning["compatible"] = True
                    warning["message"] = ("Dimensione oggetto compatibile (" +
                                          ("1 bit" if expected_bits == 1 else "1 byte") +
                                          "); DPT esatto non assegnato in ETS")
                    if len(known) < len(sizes):
                        warning["message"] += " · alcuni oggetti senza dimensione decodificata"
                    compatible += 1
                elif known:
                    warning["message"] += " · dimensione oggetto INCOMPATIBILE con il DPT atteso"
                else:
                    warning["message"] += " · DPT non assegnato; dimensione oggetti non disponibile"
    pending = sum(not w.get("verified", False) for w in warnings)
    return {"format": "nm-studio-ha-knx-preview", "version": 1, "read_only": True,
            "applied": False, "requires_installer_approval": True,
            "project": layout["project"], "counts": {key: len(value) for key, value in entries.items()},
            "warnings": warnings, "checks_confirmed": confirmed, "checks_compatible": compatible,
            "checks_pending": pending,
            "evidence_used": evidence is not None, "yaml": "\n".join(lines) + "\n"}

