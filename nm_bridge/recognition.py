"""Explainable KNX ETS recognition reviews; no bus or Home Assistant writes.

Names are hints, never proof. Reviews do not change the existing suggestion
contracts, which remain installer-confirmed and purely provisional.
"""

import re


FUNCTION_FIELDS = {
    "light": {"command": "1.001", "feedback": "1.001"},
    "dimmer": {"command": "1.001", "feedback": "1.001", "relative": "3.007",
               "brightness": "5.001", "brightness_feedback": "5.001"},
    "cover": {"command": "1.008", "stop": "1.007", "position": "5.001"},
    "climate": {"command": "9.001", "temperature": "9.001",
                "target_temperature_state": "9.001", "heat_cool": "1.100",
                "heat_cool_state": "1.100", "operation_mode": "20.102",
                "operation_mode_state": "20.102"},
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
                expected_bits = _expected_bits(expected)
                if assigned:
                    status = "verified_dpt" if assigned == expected else "conflict_dpt"
                elif known and expected_bits and all(bit == expected_bits for bit in known):
                    status = "compatible_size"
                elif known and expected_bits:
                    status = "conflict_size"
                else:
                    status = "dpt_unknown"
                if status.startswith("conflict"):
                    questions.append("Verifica DPT e oggetti di " + field + " (" + group + ")")
                elif status in ("dpt_unknown", "compatible_size"):
                    questions.append("Conferma DPT " + expected + " per " + field + " (" + group + ")")
            checks.append({"field": field, "address": group, "expected_dpt": expected, "status": status})
            strength.append(status)
        # A high score is an evidence grade, NEVER permission to create or control entities.
        confidence = ("bassa" if any(s in ("unlinked", "missing", "conflict_dpt", "conflict_size") for s in strength)
                      else "alta" if strength and all(s == "verified_dpt" for s in strength) and not questions
                      else "media" if strength and all(s in ("verified_dpt", "compatible_size") for s in strength)
                      else "bassa")
        output.append({"name": candidate.get("name", "")[:80], "kind": kind,
                       "command": candidate.get("command"), "confidence": confidence,
                       "checks": checks, "questions": questions[:12], "installer_confirmation_required": True})
    return output
