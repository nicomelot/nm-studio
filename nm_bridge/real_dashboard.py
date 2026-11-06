"""Native dashboard navigation for reviewed real entity bindings."""
import hashlib
import json

def _location(room):
    """Short display labels never replace the complete room identity."""
    parts = [p.strip() for p in room.split('/') if p.strip()]
    if len(parts) >= 3:
        return tuple(parts[:2]), ' / '.join(parts[2:])
    if len(parts) == 2:
        if parts[1].lower().startswith('piano ') or parts[1].lower() in {'interrato', 'seminterrato', 'terra', 'primo', 'secondo'}:
            return tuple(parts), 'Generali'
        return (parts[0], 'Zone'), parts[1]
    return (), room


def _floor_name(key):
    if not key:
        return 'Altre zone'
    name = key[-1]
    if name.lower().startswith('piano '):
        name = name[6:]
    return name.capitalize() if name.isupper() else name


def _room_icon(name):
    for words, icon in [(('bagno', 'wellness'), 'mdi:shower'),
                        (('camera',), 'mdi:bed-outline'),
                        (('cucina',), 'mdi:silverware-fork-knife'),
                        (('garage',), 'mdi:garage'),
                        (('soggiorno', 'sala'), 'mdi:sofa-outline'),
                        (('ufficio',), 'mdi:desk'),
                        (('palestra',), 'mdi:dumbbell')]:
        if any(word in name.lower() for word in words):
            return icon
    return 'mdi:door-open'


def render_dashboard(approved, url_path):
    rooms, categories = {}, {}
    for item in approved:
        card = item['card']
        room = item['room']
        category = {'Illuminazione': 'Luci', 'Schermature': 'Motorizzazioni',
                    'Climatizzazione': 'Clima'}.get(item['category'], item['category'])
        rooms.setdefault(room, []).append(card)
        categories.setdefault(category, {}).setdefault(room, []).append(card)
    total = len(approved)
    def route(prefix, identity):
        return prefix + '-' + hashlib.sha256(identity.encode()).hexdigest()[:12]

    def button(title, path, icon='mdi:arrow-right'):
        return {'type': 'button', 'name': title, 'icon': icon, 'icon_height': '32px',
                'grid_options': {'columns': 12, 'rows': 2},
                'tap_action': {'action': 'navigate', 'navigation_path': '/' + url_path + '/' + path}}

    def view(title, path, sections, parent=None):
        result = {'title': title, 'path': path, 'type': 'sections', 'max_columns': 3, 'sections': sections}
        if parent:
            result.update(subview=True, back_path='/' + url_path + '/' + parent)
        return result

    def grid(cards, title=None):
        headings = [{'type': 'heading', 'heading': title, 'heading_style': 'title'}] if title else []
        return {'type': 'grid', 'cards': headings + cards}

    floors, details = {}, []
    for room in rooms:
        key, label = _location(room)
        floors.setdefault(key, []).append(room)
    buildings = {key[0] for key in floors if key}

    def floor_title(key):
        name = _floor_name(key)
        return key[0] + ' · ' + name if key and len(buildings) > 1 else name

    def floor_order(key):
        ranks = {'interrato': 0, 'seminterrato': 1, 'terra': 2, 'primo': 3, 'secondo': 4}
        return (key[0] if key else '~', ranks.get(_floor_name(key).lower(), 5), _floor_name(key))

    # Legacy imports inserted a synthetic floor. Hide only that navigation level;
    # room identities and their stable URLs remain untouched.
    def direct(key):
        return not key or key[-1].casefold() in {'altri ambienti', 'zone', 'da assegnare'}

    floor_links = []
    for key in sorted(floors, key=floor_order):
        floor_path = route('piano', json.dumps(key))
        if not direct(key):
            floor_links.append(button(floor_title(key), floor_path, 'mdi:home-floor-0'))
        zone_links = []
        for room in sorted(floors[key]):
            label = _location(room)[1]
            if direct(key) and key and len(buildings) > 1:
                label = key[0] + ' · ' + label
            path = route('stanza', room)
            zone_links.append(button(label, path, _room_icon(label)))
            sections = [grid(grouped[room], category) for category, grouped in categories.items() if room in grouped]
            details.append(view(label, path, sections, 'ambienti' if direct(key) else floor_path))
        if direct(key):
            floor_links.extend(zone_links)
        else:
            details.append(view(floor_title(key), floor_path,
                                [grid(zone_links[i:i+6]) for i in range(0, len(zone_links), 6)], 'ambienti'))

    function_links = []
    for category, grouped in categories.items():
        path = route('funzione', category)
        function_links.append(button(category, path, {'Luci': 'mdi:lightbulb-group-outline', 'Motorizzazioni': 'mdi:window-shutter', 'Clima': 'mdi:thermostat', 'Scene': 'mdi:movie-open-outline', 'Sensori': 'mdi:access-point'}.get(category, 'mdi:view-grid-outline')))
        sections = []
        for key in sorted(floors, key=floor_order):
            for room in sorted(floors[key]):
                if room in grouped:
                    sections.append(grid(grouped[room], (_location(room)[1] if direct(key) else floor_title(key) + ' · ' + _location(room)[1])))
        details.append(view(category, path, sections, 'funzioni'))

    overview = []
    for category, states, title in [('Luci', ['on'], 'Luci accese'),
                                     ('Motorizzazioni', ['open', 'opening'], 'Motorizzazioni aperte')]:
        ids = [{'entity': c['entity'], 'name': c['name']} for cards in categories.get(category, {}).values() for c in cards]
        if ids:
            overview.append({'type': 'entity-filter', 'entities': ids, 'state_filter': states,
                             'show_empty': False, 'card': {'type': 'entities', 'title': title, 'show_header_toggle': False}})
    dashboard = {'title': 'NM Control', 'views': [
        view('Home', 'panoramica', [grid([
            {'type': 'markdown', 'content': '# La casa\nImpianto reale · ' + str(total) + ' entità'},
            button('Ambienti', 'ambienti', 'mdi:floor-plan'),
            button('Funzioni', 'funzioni', 'mdi:lightbulb-group-outline')]),
            *([grid(overview)] if overview else [])]),
        view('Ambienti', 'ambienti', [grid(floor_links, 'Scegli la stanza' if all(direct(k) for k in floors) else 'Scegli il piano o la stanza')]),
        view('Funzioni', 'funzioni', [grid(function_links, 'Scegli la categoria')]), *details]}
    return dashboard
