"""Generate structured official KNX Panel create_entity drafts, without executing them."""

try:
    from .missing_ha_generator import review
except ImportError:
    from missing_ha_generator import review


CLIMATE_GROUPS = {
    "ga_heat_cool": ("heat_cool", "heat_cool_state"),
    "ga_operation_mode": ("operation_mode", "operation_mode_state"),
    "ga_on_off": ("on_off", "on_off_state"),
    "ga_controller_mode": ("controller_mode", "controller_mode_state"),
    "ga_fan_speed": ("fan_speed", "fan_speed_state"),
    "ga_fan_swing": ("swing", "swing_state"),
}


def climate_config(fields):
    if not fields.get("temperature") or not fields.get("target_temperature_state"):
        raise ValueError("Clima: temperatura rilevata e stato setpoint obbligatori")
    config = {
        "ga_temperature_current": {"state": fields["temperature"]},
        "target_temperature": {
            "ga_temperature_target": {"write": fields["command"], "state": fields["target_temperature_state"]},
        },
    }
    for group, (write, state) in CLIMATE_GROUPS.items():
        values = {role: fields[key] for role, key in (("write", write), ("state", state)) if fields.get(key)}
        if values:
            config[group] = values
    if "ga_fan_speed" in config:
        config["ga_fan_speed"]["dpt"] = "5.001"
    return config


def group_addresses(config, prefix=()):
    """Yield KNX group selectors, including the climate setpoint subsection."""
    for key, group in config.items():
        if not isinstance(group, dict):
            continue
        path = (*prefix, key)
        if key.startswith("ga_"):
            yield path, group
        else:
            yield from group_addresses(group, path)


def configured_addresses(config):
    return {value for _, group in group_addresses(config) for role, value in group.items()
            if role in ("write", "state") and isinstance(value, str)}


def build(layout, request):
    validated = review(layout, request)
    if not validated["approved_count"]:
        raise ValueError("Approve at least one device before preparing the installation")
    approved = [x for x in request["devices"] if x.get("approved") is True]
    calls = []
    for item in approved:
        original = layout["widgets"][item["index"]]
        fields = item["fields"]
        kind = original["type"]
        if not fields.get("command"):
            raise ValueError("A selected device has no KNX command address")
        if kind not in ('light', 'dimmer', 'cover', 'switch', 'button', 'climate'):
            raise ValueError('Tipo non supportato dalla creazione diretta')
        if kind == 'dimmer' and not fields.get('brightness'):
            raise ValueError('Dimmer: GA luminosità assoluta obbligatorio')
        if kind == 'cover' and not fields.get('stop'):
            raise ValueError('Tapparella: GA arresto obbligatorio per il collaudo')
        data = {"entity": {"name": item["name"].strip()}, "knx": {}}
        if kind == "climate":
            data["knx"] = climate_config(fields)
            calls.append({"type": "knx/create_entity", "platform": "climate", "data": data})
            continue
        if kind == "button":
            platform = "button"
            mapping = {"command": ("ga_send", "write")}
            # HA accepts raw short payloads with length 0 for 1-bit values.
            data["knx"]["data"] = {
                "payload": "0x0" if original.get("command_mode") == "off_only" else "0x1",
                "payload_length": 0,
            }
        elif kind == "switch":
            platform = "switch"
            mapping = {"command": ("ga_switch", "write"), "feedback": ("ga_switch", "state")}
        elif kind in ("light", "dimmer"):
            platform = "light"
            mapping = {"command": ("ga_switch", "write"), "feedback": ("ga_switch", "state"),
                       "brightness": ("ga_brightness", "write"), "brightness_feedback": ("ga_brightness", "state")}
        else:
            platform = "cover"
            # A generic 'position' field is not a verified position *command*;
            # never map it to position_address without ETS evidence.
            mapping = {"command": ("ga_up_down", "write"), "stop": ("ga_stop", "write"),
                       "position_command": ("ga_position_set", "write"),
                       "position_feedback": ("ga_position_state", "state")}
        for key, (target, direction) in mapping.items():
            if fields.get(key):
                data["knx"].setdefault(target, {})[direction] = fields[key]
        calls.append({"type": "knx/create_entity", "platform": platform, "data": data})
    return {"format": "nm-studio-knx-panel-create-plan", "version": 1,
            "source_fingerprint": validated["source_fingerprint"],
            "approved_count": len(calls), "calls": calls, "executed": False,
            "requires_admin": True, "requires_live_knx_integration": True,
            "requires_validation": True,
            "limitations": [
                "Queste sono richieste di anteprima; l'add-on non le invia a Home Assistant.",
                "Le API KNX Panel richiedono autorizzazioni amministratore e un'integrazione KNX attiva.",
                "Controllare DPT, GA già esistenti e backup prima di creare entità.",
                "I campi posizione tapparella non verificati non sono inclusi nelle richieste.",
            ]}

