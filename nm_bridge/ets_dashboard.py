"""Plan an editable Home Assistant dashboard from a saved ETS project."""

import hashlib
import json

try:
    from .real_dashboard import dashboard_path, render_dashboard
except ImportError:
    from real_dashboard import dashboard_path, render_dashboard


FUNCTIONS = {
    'light': ('Illuminazione', 'mdi:lightbulb-outline'),
    'dimmer': ('Illuminazione', 'mdi:lightbulb-on-outline'),
    'cover': ('Schermature', 'mdi:window-shutter'),
    'climate': ('Climatizzazione', 'mdi:thermostat'),
    'scene': ('Scene', 'mdi:movie-open-outline'),
    'sensor': ('Sensori', 'mdi:gauge'),
    'binary_sensor': ('Sensori', 'mdi:motion-sensor'),
}


def preview(project, record):
    if record is None:
        raise ValueError('Salva il progetto ETS prima di preparare la plancia')
    imported = record['imported']
    if imported['project_key'] != project:
        raise ValueError('Il progetto salvato non corrisponde al file ETS')

    items = []

    def add(name, room, category, icon, detail=''):
        label = f'{name} · {detail}' if detail else name
        card = {'type': 'heading', 'heading_style': 'subtitle', 'icon': icon,
                'heading': f'{label} · Da associare'}
        items.append({'card': card, 'room': room, 'category': category})

    reviews = record.get('reviews', {})
    for row in imported.get('lab_candidates', []):
        review = reviews.get(row['command'], row)
        if review['kind'] in FUNCTIONS:
            category, icon = FUNCTIONS[review['kind']]
            add(review['name'], review['room'] or 'Da assegnare', category, icon, row['command'])
    functions = len(items)

    units = imported.get('hvac_units', [])
    shared = 0
    for unit in units:
        climate = unit['kind'] == 'climate'
        category = 'Climatizzazione' if climate else 'Locale tecnico'
        icon = 'mdi:thermostat' if climate else 'mdi:hvac'
        name = unit['name'] if unit['name'] != 'Dispositivo' else unit['model']
        address = unit['individual_address']
        common = sum(point['shared_hvac'] for point in unit['points'])
        shared += bool(common)
        detail = f'{address} · {common} GA condivisi' if common else address
        for room in unit['rooms'] or ['Da assegnare']:
            add(name, room, category, icon, detail)

    if not items:
        raise ValueError('Il progetto ETS non contiene funzioni riconosciute per la plancia')

    # Use the same destination and view identities as the online generator.
    # The existing reviewed update path preserves manual dashboard edits.
    url_path = dashboard_path(project)
    dashboard = render_dashboard(
        items, url_path,
        intro='**Bozza da ETS**\n\nCollega le entità KNX in NM Control per abilitare i comandi.',
    )
    title = ('NM Control · ' + record['label'])[:60].rstrip()
    dashboard['title'] = title
    fingerprint = hashlib.sha256(json.dumps(dashboard, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {
        'title': title, 'url_path': url_path, 'dashboard': dashboard, 'fingerprint': fingerprint,
        'summary': {'tiles': 0, 'planned': len(items), 'rooms': len({item['room'] for item in items}),
                    'functions': functions, 'climate': sum(unit['kind'] == 'climate' for unit in units),
                    'gateways': sum(unit['kind'] != 'climate' for unit in units), 'shared': shared},
        'warnings': [],
    }
