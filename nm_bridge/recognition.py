"""Explainable KNX ETS recognition reviews; no bus or Home Assistant writes.

Names are hints, never proof. Reviews do not change the existing suggestion
contracts, which remain installer-confirmed and purely provisional.
"""

import re
try:
    from .ets_named_functions import application_stop
except ImportError:
    from ets_named_functions import application_stop


FUNCTION_FIELDS = {
    "light": {"command": "1.001", "feedback": ("1.001", "1.011")},
    "dimmer": {"command": "1.001", "feedback": ("1.001", "1.011"), "relative": "3.007",
               "brightness": "5.001", "brightness_feedback": "5.001",
               "color_temperature": "7.600", "color_temperature_feedback": "7.600"},
    "cover": {"command": "1.008", "stop": ("1.007", "1.017"),
              "position": "5.001", "position_command": "5.001", "position_feedback": "5.001",
              "slats": "5.001", "slats_feedback": "5.001"},
    "climate": {"command": "9.001", "temperature": "9.001",
                "target_temperature_state": "9.001", "heat_cool": "1.100",
                "heat_cool_state": "1.100", "operation_mode": "20.102",
                "operation_mode_state": "20.102", "humidity": ("9.007", "5.001"),
                "heating_demand": "1.001", "valve_state": ("1.011", "1.001")},
}


def _dpt(value):
    raw = str(value or "").upper().replace(" ", "")
    match = re.fullmatch(r"(?:DPST-|DPT-)(\d+)[.-](\d+)", raw)
    return f"{int(match.group(1))}.{int(match.group(2)):03d}" if match else ""


def _size(connection):
    value = str(connection.get("size", "")).lower().replace(" ", "")
    return {"1bit": 1, "4bit": 4, "1byte": 8, "2bytes": 16, "2byte": 16}.get(value)


def _expected_bits(dpt):
    return {"1": 1, "3": 4, "5": 8, "9": 16, "20": 8}.get(dpt.split(".", 1)[0])


HVAC_ROLES = (
    ("flap", r"\b(?:flap|swing|alette|deflettor|oscillazion)\w*\b"),
    ("fan_speed", r"\b(?:fan\s*speed|ventilator\w*|velocit[aà]\s*(?:ventol|aria)|fan\s*level)\w*"),
    ("humidity", r"\b(?:umidit[aà]|humidity|humidit[yé])\b"),
    ("setpoint", r"\b(?:setpoint|temperatura\s*(?:impostata|desiderata)|target\s*temp)\b"),
    ("temperature", r"\b(?:temperatura\s*(?:ambiente|attuale|misurata)|room\s*temp|actual\s*temp)\b"),
    ("mode", r"\b(?:modalit[aà]|operating\s*mode|hvac\s*mode|heat\s*/\s*cool|estate\s*/\s*inverno)\b"),
    ("ventilation", r"\b(?:portata\s*aria|air\s*flow|ricambio\s*aria|bypass|recuperatore)\b"),
)


def hvac_address_inventory(addresses):
    """Identify possible HVAC/VMC GA semantics without guessing proprietary DPTs.

    This is an independent read-only inventory, not a device/entity proposal.
    Manufacturer-specific fan levels, swing positions and modes must be mapped
    only after the installer supplies the corresponding application semantics.
    """
    result = []
    for address in addresses[:6000]:
        name = " ".join(str(address.get(field) or "") for field in ("name", "description"))
        objects = " ".join(str(obj.get(field) or "") for obj in address.get("connections", [])[:12]
                           for field in ("name", "function"))
        combined = f"{name} {objects}"
        if not re.search(r"\b(?:hvac|clima|climatizz|termostat|daikin|zennio|intesis|vmc|ventilazion|"
                         r"recuperator|fan\s*coil|fancoil|condizionator)\w*\b", combined, re.I):
            continue
        roles = [role for role, pattern in HVAC_ROLES if re.search(pattern, combined, re.I)]
        if not roles:
            continue
        dpt = _dpt(address.get("dpt"))
        linked = bool(address.get("linked"))
        result.append({"address": address.get("address"), "name": str(address.get("name") or "")[:160],
                       "roles": roles, "dpt": dpt, "linked": linked,
                       "status": "da_verificare" if linked else "non_collegato",
                       "question": ("Verificare ruolo, direzione, DPT e codifica dei valori in ETS"
                                    if linked else "Verificare se questo GA è effettivamente utilizzato")})
    return result[:300]


def review_suggestions(addresses, suggestions):
    """Bounded, deterministic per-field evidence and explicit installer questions."""
    lookup = {a["address"]: a for a in addresses}
    output = []
    for candidate in suggestions[:300]:
        kind = candidate.get("kind", "unknown")
        checks = []
        questions = []
        strength = []
        for field, expected in FUNCTION_FIELDS.get(kind, {"command": ""}).items():
            allowed = (expected,) if isinstance(expected, str) else expected
            expected_label = " / ".join(allowed)
            group = candidate.get(field)
            if not group:
                if field in ("command", "temperature", "target_temperature_state"):
                    questions.append("Qual è l'indirizzo di " + field.replace("_", " ") + "?")
                continue
            item = lookup.get(group)
            status = "missing"
            if not item or not item.get("linked"):
                status = "unlinked"
                questions.append("Il GA " + group + " per " + field + " è realmente collegato in ETS?")
            else:
                assigned = _dpt(item.get("dpt"))
                bits = [_size(c) for c in item.get("connections", [])]
                known = [bit for bit in bits if bit is not None]
                expected_bits = {_expected_bits(value) for value in allowed}
                if assigned:
                    status = "verified_dpt" if assigned in allowed else "conflict_dpt"
                    if kind == 'cover' and field == 'stop' and assigned == '1.008' and application_stop(item):
                        status = 'compatible_object'
                elif known and None not in expected_bits and all(bit in expected_bits for bit in known):
                    status = "compatible_size"
                elif known and None not in expected_bits:
                    status = "conflict_size"
                else:
                    status = "dpt_unknown"
                if status.startswith("conflict"):
                    questions.append("Verifica DPT e oggetti di " + field + " (" + group + ")")
                elif status == 'compatible_object':
                    questions.append('Stop ' + group + ': DPT 1.008 confermato dall’oggetto applicativo; collaudare l’arresto')
                elif status in ("dpt_unknown", "compatible_size"):
                    questions.append("Conferma DPT " + expected_label + " per " + field + " (" + group + ")")
            checks.append({"field": field, "address": group, "expected_dpt": expected_label, "status": status})
            strength.append(status)
        # A high score is an evidence grade, NEVER permission to create or control entities.
        confidence = ("bassa" if any(s in ("unlinked", "missing", "conflict_dpt", "conflict_size") for s in strength)
                      else "alta" if strength and all(s == "verified_dpt" for s in strength) and not questions
                      else "media" if strength and all(s in ("verified_dpt", "compatible_size", "compatible_object") for s in strength)
                      else "bassa")
        output.append({"name": candidate.get("name", "")[:80], "kind": kind,
                       "command": candidate.get("command"), "confidence": confidence,
                       "checks": checks, "questions": questions[:12], "installer_confirmation_required": True})
    return output

