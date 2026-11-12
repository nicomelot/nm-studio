"""Installer initiated, single-entity tests through HA services; never raw telegrams."""
try:
    from .dashboard_publisher import HAWebSocket
    from .installation_review import compare
    from .missing_ha_generator import fingerprint
    from .widget_layout import read_layout, LAYOUT_LOCK
except ImportError:
    from dashboard_publisher import HAWebSocket
    from installation_review import compare
    from missing_ha_generator import fingerprint
    from widget_layout import read_layout, LAYOUT_LOCK


def command(payload, connection_factory=HAWebSocket):
    if not isinstance(payload, dict) or payload.get('confirm') is not True:
        raise ValueError('Abilita il collaudo prima di inviare comandi reali')
    with LAYOUT_LOCK:
        layout = read_layout()
        if payload.get('source_fingerprint') != fingerprint(layout):
            raise ValueError('Configurazione cambiata: aggiorna elenco')
        index = payload.get('index')
        if type(index) is not int or not 0 <= index < len(layout.get('widgets', [])):
            raise ValueError('Funzione non valida')
        widget = layout['widgets'][index]
        ident = widget.get('entity_id')
        if not ident or ident != payload.get('entity_id') or '.nm_lab_' in ident:
            raise ValueError('Associazione reale non verificata')
        kind, action = widget['type'], payload.get('action')
        off_only = kind == 'light' and widget.get('command_mode') == 'off_only'
        if off_only and action != 'off':
            raise ValueError('Questo pulsante consente solo lo spegnimento')
        allowed = {'light': {'on': 'turn_on', 'off': 'turn_off'},
                   'dimmer': {'on': 'turn_on', 'off': 'turn_off', 'brightness': 'turn_on'},
                   'cover': {'open': 'open_cover', 'stop': 'stop_cover', 'close': 'close_cover'},
                   'switch': {'on': 'turn_on', 'off': 'turn_off'},
                   'button': {'press': 'press'}}
        if action not in allowed.get(kind, {}):
            raise ValueError('Comando non consentito per questa funzione')
        data = {}
        if action == 'brightness':
            value = payload.get('value')
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError('Luminosità richiesta tra 0 e 100')
            data['brightness_pct'] = value
        with connection_factory() as ws:
            checked = compare(layout, index, ws)
            if checked['status'] != 'present':
                raise ValueError('Completa o verifica la configurazione prima del collaudo')
            states = ws.call('get_states')
            if not isinstance(states, list):
                raise ValueError('Stati HA non disponibili')
            state = next((s for s in states if s.get('entity_id') == ident), None)
            unknown_allowed = kind in ('button', 'switch') and state and state.get('state') == 'unknown'
            if not state or (state.get('state') in ('unknown', 'unavailable') and action != 'stop'
                             and not off_only and not unknown_allowed):
                raise ValueError('Stato non disponibile: controlla connessione e diagnostica')
            attrs = state.get('attributes') or {}
            if kind == 'cover':
                required = {'open': 1, 'close': 2, 'stop': 8}[action]
                if not isinstance(attrs.get('supported_features'), int) or not attrs['supported_features'] & required:
                    raise ValueError('Comando non supportato dall’entità HA')
            if action == 'brightness' and not set(attrs.get('supported_color_modes') or []).difference({'onoff', 'unknown'}):
                raise ValueError('Questa entità HA non espone ancora la regolazione luminosa')
            ws.call('call_service', domain='light' if kind == 'dimmer' else kind,
                    service=allowed[kind][action], target={'entity_id': ident}, service_data=data)
            return {'sent': True, 'entity_id': ident, 'action': action,
                    'message': 'Comando accettato da HA. Verifica il dispositivo e rileggi lo stato; esito fisico non confermato.'}
