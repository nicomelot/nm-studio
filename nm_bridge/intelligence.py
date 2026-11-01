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
            # HA last_changed only moves when the value changes. A constant
            # battery SOC is not evidence of a disconnected MQTT device.
            updated = _timestamp(entry.get("last_updated"))
            changed = _timestamp(entry.get("last_changed"))
            stamp = updated or changed
            age = (now - stamp).total_seconds() if stamp else None
            fresh = age is not None and -5 <= age <= 120
            age_minutes = round(max(0, age) / 60, 1) if age is not None and math.isfinite(age) else None
            health = "recent" if fresh else "unknown" if stamp is None else "old_update"
            found[key] = {"key": key, "label": label, "value": round(value, 2),
                          "unit": unit, "fresh": fresh, "simulated": True,
                          "health": health, "age_minutes": age_minutes,
                          "last_updated": updated.isoformat() if updated else None,
                          "last_changed": changed.isoformat() if changed else None}
    return [found[key] for key, *_ in TELEMETRY if key in found]


def summarize(states, now=None):
    now = now or datetime.now(timezone.utc)
    base = {"read_only": True, "source": "Home Assistant", "found": False,
            "contract_version": 1,
            "capabilities": {"supervision": True, "decision_engine": False,
                             "simulation": False, "history": False,
                             "commands": False, "provider": "home_assistant_states"},
            "valid": False, "status": "not_found", "summary": "Nessuna decisione di simulazione presente negli stati Home Assistant.",
            "decision_id": None, "generated_at": None, "expires_at": None,
            "proposals": [], "telemetry": [], "warnings": [], "explanation_facts": [],
            "execution_enabled": False}
    if not isinstance(states, list):
        return base
    base["telemetry"] = _telemetry(states, now)
    values = {item["key"]: item for item in base["telemetry"]}
    pv, load = values.get("pv"), values.get("load")
    if pv and load and pv["fresh"] and load["fresh"]:
        base["explanation_facts"].append({"label": "Bilancio simulato FV − consumi", "value": round(pv["value"] - load["value"], 2), "unit": "W"})
    if values.get("battery"):
        base["explanation_facts"].append({"label": "Carica batteria simulata", "value": values["battery"]["value"], "unit": "%"})
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
    # Discovery is based on the validated simulation schema, not on hostnames,
    # Proxmox, model names or local network endpoints.
    base["capabilities"] = {**base["capabilities"], "decision_engine": True,
                             "simulation": True}
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
