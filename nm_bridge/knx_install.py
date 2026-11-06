"""One acknowledged installation step, with immediate durable widget association."""

try:
    from .widget_layout import LAYOUT_LOCK, read_layout, save_layout
    from .missing_ha_generator import fingerprint
    from .knx_panel_apply import create_one
except ImportError:
    from widget_layout import LAYOUT_LOCK, read_layout, save_layout
    from missing_ha_generator import fingerprint
    from knx_panel_apply import create_one


def install_step(payload, create=create_one):
    # Serialize provisioning and widget writes. An interrupted request must never
    # overwrite a newer project, or race another creation of the same function.
    with LAYOUT_LOCK:
        layout = read_layout()
        result = create(layout, payload)
        chosen = [item for item in payload['review']['devices'] if item.get('approved') is True]
        item = chosen[payload['call_index']]
        widget = layout['widgets'][item['index']]
        widget.update(name=item['name'].strip(), fields=item['fields'], entity_id=result['entity_id'])
        try:
            save_layout({**layout, 'confirm': True})
        except (OSError, ValueError):
            # Creation already happened in HA. Never report this as safe to retry.
            return {**result, 'linked': False, 'stop': True,
                    'message': 'Entità creata in HA, associazione non salvata. Associa questa entità esistente prima di proseguire.'}
        return {**result, 'linked': True, 'stop': False,
                'source_fingerprint': fingerprint(read_layout())}
