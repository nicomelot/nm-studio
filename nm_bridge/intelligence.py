"""Read-only projection of simulated decisions exposed by Home Assistant.

This module never connects to MQTT, executes Home Assistant services, or
translates proposed actions into executable commands.
"""

from datetime import datetime, timezone


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def summarize(states, now=None):
    now = now or datetime.now(timezone.utc)
    base = {"read_only": True, "source": "Home Assistant", "found": False,
            "valid": False, "status": "not_found", "summary": "Nessuna decisione di simulazione presente negli stati Home Assistant.",
            "generated_at": None, "expires_at": None, "proposals": [], "warnings": [],
            "execution_enabled": False}
    if not isinstance(states, list):
        return base
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
