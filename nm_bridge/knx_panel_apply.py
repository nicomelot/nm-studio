"""Opt-in creation of one installer-approved entity through the official KNX panel.

This changes HA configuration and can cause subsequent KNX bus reads. Never
execute without a fresh installer review, a matching plan and explicit consent.
"""

try:
    from .knx_entity_plan import build
    from .dashboard_publisher import HAWebSocket
except ImportError:
    from knx_entity_plan import build
    from dashboard_publisher import HAWebSocket


class KNXApplyError(ValueError):
    pass


def create_one(layout, payload, connection_factory=HAWebSocket):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise KNXApplyError("Conferma esplicita richiesta")
    if payload.get("backup_confirmed") is not True or payload.get("ets_confirmed") is not True:
        raise KNXApplyError("Verifica ETS e backup Home Assistant obbligatori")
    review = payload.get("review")
    plan = build(layout, review)
    if plan["source_fingerprint"] != payload.get("source_fingerprint"):
        raise KNXApplyError("Progetto cambiato: rigenera il piano di creazione")
    index = payload.get("call_index")
    if type(index) is not int or not 0 <= index < len(plan["calls"]):
        raise KNXApplyError("Seleziona un solo dispositivo presente nel piano")
    call = plan["calls"][index]
    expected = payload.get("expected_call")
    if expected != call:
        raise KNXApplyError("La configurazione del dispositivo è cambiata: ripeti la verifica")

    with connection_factory() as ws:
        base = ws.call("knx/get_base_data")
        if not isinstance(base, dict):
            raise KNXApplyError("Integrazione KNX non verificabile")
        platforms = base.get("supported_platforms", [])
        if call["platform"] not in platforms:
            raise KNXApplyError("La piattaforma non è supportata dall'integrazione KNX")
        used = ws.call("knx/get_entities_by_group")
        if not isinstance(used, dict):
            raise KNXApplyError("Indice dei GA KNX non interpretabile: creazione annullata")
        addresses = {value for group in call["data"]["knx"].values()
                     if isinstance(group, dict) for key, value in group.items()
                     if key in ("write", "state") and isinstance(value, str)}
        overlaps = sorted(addresses.intersection(used))
        if overlaps:
            raise KNXApplyError("GA già presente in KNX Home Assistant: " + ", ".join(overlaps))
        validated = ws.call("knx/validate_entity", platform=call["platform"], data=call["data"])
        if not isinstance(validated, dict) or validated.get("success") is not True:
            detail = validated.get("error_base", "Formato non accettato") if isinstance(validated, dict) else "Risposta non valida"
            raise KNXApplyError("Validazione KNX rifiutata: " + str(detail)[:110])
        created = ws.call("knx/create_entity", platform=call["platform"], data=call["data"])
        if not isinstance(created, dict) or created.get("success") is not True or not created.get("entity_id"):
            raise KNXApplyError("Home Assistant non ha confermato la creazione: verifica nel pannello KNX")
        return {"created": True, "entity_id": created["entity_id"],
                "name": call["data"]["entity"]["name"], "platform": call["platform"],
                "note": "Entità creata in HA. I comandi sul bus restano da collaudare."}

