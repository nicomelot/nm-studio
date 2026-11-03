"""Read bounded pages from the HA 2026.10 KNX telegram store."""
from datetime import datetime, timedelta, timezone
import re
try:
    from .dashboard_publisher import HAWebSocket
    from .bus_recorder import addresses
except ImportError:
    from dashboard_publisher import HAWebSocket
    from bus_recorder import addresses


def query(payload, client_factory=HAWebSocket, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        raise ValueError('Richiesta storico non valida')
    offset = payload.get('offset', 0)
    if type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError('Pagina storico non valida')
    if 'end' in payload and not isinstance(payload['end'], str):
        raise ValueError('Data non valida')
    end = datetime.fromisoformat(payload['end'].replace('Z', '+00:00')) if payload.get('end') else now
    if end.tzinfo is None or end > now + timedelta(minutes=1) or end < now - timedelta(days=30):
        raise ValueError('Data non valida: scegli gli ultimi 30 giorni')
    start = end - timedelta(hours=48)
    ga = payload.get('ga', '')
    source = payload.get('source', '')
    if ga:
        addresses([ga])
    if source and (not isinstance(source, str) or not re.fullmatch(r'(?:[0-9]|1[0-5])\.(?:[0-9]|1[0-5])\.(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])', source)):
        raise ValueError('Indirizzo fisico non valido')
    base = {'start': start.isoformat(), 'end': end.isoformat(), 'offset': offset,
            'page_size': 500, 'read_only': True, 'knx_traffic': False}
    try:
        with client_factory() as client:
            info = client.call('knx/get_base_data')
            result = client.call('knx/query_telegrams', start_time=base['start'], end_time=base['end'],
                                 limit=500, offset=offset, order_descending=True,
                                 destinations=[ga] if ga else [], sources=[source] if source else [])
        if not isinstance(result, dict) or not isinstance(result.get('telegrams'), list) or len(result['telegrams']) > 500:
            raise ValueError('Risposta storico non riconosciuta')
        retention = (info.get('connection_info') or {}).get('telegram_retention') if isinstance(info, dict) else None
        return {**base, 'available': True, 'items': result['telegrams'], 'total': result.get('total_count'),
                'has_more': bool(result.get('limit_reached')), 'retention_days': retention,
                'note': 'Intervallo richiesto di 48 ore, non copertura certificata. Dipende dalla conservazione HA, dai limiti di eventi e dalla continuità della connessione. Esportazione della pagina corrente (massimo 500 eventi).'}
    except Exception:
        return {**base, 'available': False, 'items': [], 'has_more': False,
                'note': 'Storico KNX HA non accessibile: richiede API compatibile, archivio attivo e permessi amministratore. I privilegi dell’add-on non sono stati aumentati. Consulta il pannello KNX di HA o usa il registro locale.'}
