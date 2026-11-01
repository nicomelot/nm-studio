"""Read-only projection of simulated decisions exposed by Home Assistant.

This module never connects to MQTT, executes Home Assistant services, or
translates proposed actions into executable commands.
"""

import math
from datetime import datetime, timezone


TELEMETRY = (
    ("pv", "Produzione FV SIM", "FV", "W", 0, 30000),
    ("load", "Consumo casa SIM", "Consumi", "W", 0, 30000),
    ("battery", "Batteria SIM", "Batteria", "%", 0, 100),
    ("temperature", "Temperatura PT SIM", "Temperatura PT", "°C", -20, 60),
    ("humidity", "Umidita PT SIM", "Umidità PT", "%", 0, 100),
    ("co2", "CO2 PT SIM", "CO₂ PT", "ppm", 250, 10000),
)


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _telemetry(states, now):
    """Select only known simulated HA sensors; never infer real plant values."""
    found = {}
    for entry in states:
        if not isinstance(entry, dict) or not str(entry.get("entity_id", "")).startswith("sensor."):
            continue
        attrs = entry.get("attributes")
        if not isinstance(attrs, dict):
            continue
        friendly = str(attrs.get("friendly_name", "")).strip().casefold()
        for key, name, label, unit, low, high in TELEMETRY:
            # MQTT Discovery may prepend the device name to the entity name.
            if friendly != name.casefold() and not friendly.endswith(" " + name.casefold()):
                continue
            try:
                value = float(entry.get("state", ""))
            except (ValueError, TypeError, OverflowError):
                continue
            if not math.isfinite(value) or not low <= value <= high:
                continue
            stamp = _timestamp(entry.get("last_updated") or entry.get("last_changed"))
            fresh = stamp is not None and -5 <= (now - stamp).total_seconds() <= 120
            found[key] = {"key": key, "label": label, "value": round(value, 2),
                          "unit": unit, "fresh": fresh, "simulated": True}
    return [found[key] for key, *_ in TELEMETRY if key in found]


def summarize(states, now=None):
    now = now or datetime.now(timezone.utc)
    base = {"read_only": True, "source": "Home Assistant", "found": False,
            "valid": False, "status": "not_found", "summary": "Nessuna decisione di simulazione presente negli stati Home Assistant.",
            "decision_id": None, "generated_at": None, "expires_at": None,
            "proposals": [], "telemetry": [], "warnings": [],
            "execution_enabled": False}
    if not isinstance(states, list):
        return base
    base["telemetry"] = _telemetry(states, now)
    candidates = []
    for entry in states:
        if not isinstance(entry, dict) or not str(entry.get("entity_id", "")).startswith("sensor."):
            continue
        attrs = entry.get("attributes")
        if not isinstance(attrs, dict):
            continue
        # A decision is identified by its schema, not by a guessed entity_id.
        if not isinstance(attrs.get("decision_id"), str) or attrs.get("simulation") is not True:
            continue
        if not isinstance(attrs.get("actions"), list) or not isinstance(attrs.get("status"), str):
            continue
        when = _timestamp(attrs.get("generated_at"))
        if when is not None:
            candidates.append((when, attrs))
    if not candidates:
        return base
    _, decision = max(candidates, key=lambda c: c[0])
    result = {**base, "found": True,
              "decision_id": decision.get("decision_id", "")[:80],
              "status": str(decision.get("status", "unknown"))[:80],
              "summary": str(decision.get("summary", ""))[:320],
              "generated_at": decision.get("generated_at"),
              "expires_at": decision.get("expires_at")}
    expires = _timestamp(decision.get("expires_at"))
    if expires is None or expires <= now:
        result["warnings"].append("Decisione scaduta o senza scadenza verificabile.")
    if decision.get("execution_enabled") is not False:
        result["warnings"].append("Stato di esecuzione non sicuro o non dichiarato: proposte nascoste.")
    if result["warnings"]:
        return result
    result["valid"] = True
    for action in decision["actions"][:20]:
        if not isinstance(action, dict) or action.get("proposal_only") is not True or action.get("requires_confirmation") is not True:
            result["warnings"].append("Proposta con schema non sicuro: ignorata.")
            continue
        result["proposals"].append({
            "action": str(action.get("action", ""))[:80],
            "reason": str(action.get("reason", ""))[:120],
            "explanation": str(action.get("explanation", ""))[:400],
            "priority": action.get("priority") if type(action.get("priority")) is int else None,
        })
    return result
