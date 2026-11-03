"""Generate structured official KNX Panel create_entity drafts, without executing them."""

try:
    from .missing_ha_generator import review
except ImportError:
    from missing_ha_generator import review


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
        if kind not in ('light', 'dimmer', 'cover'):
            raise ValueError('Creazione diretta supportata solo per luci, dimmer e tapparelle')
        if kind == 'dimmer' and not fields.get('brightness'):
            raise ValueError('Dimmer: GA luminosità assoluta obbligatorio')
        if kind == 'cover' and not fields.get('stop'):
            raise ValueError('Tapparella: GA arresto obbligatorio per il collaudo')
        data = {"name": item["name"].strip()}
        if kind in ("light", "dimmer"):
            platform = "light"
            mapping = {"command": "address", "feedback": "state_address",
                       "brightness": "brightness_address", "brightness_feedback": "brightness_state_address"}
        else:
            platform = "cover"
            # A generic 'position' field is not a verified position *command*;
            # never map it to position_address without ETS evidence.
            mapping = {"command": "move_long_address", "stop": "stop_address"}
        for key, target in mapping.items():
            if fields.get(key):
                data[target] = fields[key]
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

