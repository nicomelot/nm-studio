"""Pure, intentionally conservative KNX-function to HA-action interpreter."""

FUNCTIONS = {"auto", "switch", "dimmer_relative", "cover_move", "scene_activate"}


def interpret(link, value, kind):
    """Return a hypothetical effect, never execute a Home Assistant action."""
    ident = link["entity_id"]
    domain = ident.split(".", 1)[0]
    function = link.get("function", "auto")
    if function == "auto" and link["dpt"] == "1.001" and domain in ("light", "switch"):
        function = "switch"
    if function == "switch":
        return {"target": "home_assistant", "domain": domain,
                "service": "turn_on" if value else "turn_off", "entity_id": ident}
    if function == "cover_move":
        return {"target": "home_assistant", "domain": "cover",
                "service": "close_cover" if value else "open_cover", "entity_id": ident,
                "note": "KNX UP=0, DOWN=1; verify inversion and actuator parameters"}
    if function == "dimmer_relative":
        direction, code = value["direction"], value["step_code"]
        if direction == "stop":
            return {"target": "no_action", "reason": "Stop/release has no equivalent safe single-step light action; use a stateful dimming adapter"}
        percentage = max(1, round(100 / (2 ** (code - 1))))
        return {"target": "home_assistant", "domain": "light", "service": "turn_on",
                "entity_id": ident, "data": {"brightness_step_pct": percentage if direction == "up" else -percentage},
                "note": "Approximate one-shot step only; hold/repeat/stop semantics require a stateful adapter"}
    if function == "scene_activate":
        if value != link["scene_number"]:
            return {"target": "no_action", "reason": "Received scene number does not match assigned scene"}
        return {"target": "home_assistant", "domain": "scene", "service": "turn_on", "entity_id": ident}
    return {"target": "ha_event_only", "entity_id": ident,
            "value": value, "reason": "No safe HA service mapping defined for this DPT/function"}
