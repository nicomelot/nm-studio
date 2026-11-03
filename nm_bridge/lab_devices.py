"""Virtual-only HA entities. ETS addresses are identifiers, never bus targets."""

import hashlib
import json
import re

KINDS = {"light", "dimmer", "cover", "scene", "sensor", "binary_sensor", "climate"}
GA = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")


def building_location(preview, command):
    """Physical common location, only a LAB proposal, never a bus assignment."""
    devices = {d['id']: d.get('ets_id') for d in preview.get('devices', [])}
    locations = {}
    for space in preview.get('building', []):
        for ref in space.get('devices', []):
            locations.setdefault(ref, []).append(space['path'])
    record = next((a for a in preview.get('addresses', []) if a['address'] == command), {})
    connections = record.get('connections', [])
    if not connections:
        return None
    paths = []
    for connection in connections:
        found = locations.get(devices.get(connection.get('device_id')), [])
        if len(found) != 1:
            return None
        parts = found[0].split(' / ')
        # Installation containers are not functional rooms.
        while parts and re.search(r'quadro|scatola|pulsantier|derivazione', parts[-1], re.I):
            parts.pop()
        paths.append(parts)
    common = []
    for level in zip(*paths):
        if len(set(level)) != 1:
            break
        common.append(level[0])
    # A building alone provides no useful room/floor assignment.
    return ' / '.join(common) if len(common) >= 2 else None


def candidates(preview):
    """Separate lab proposals; never promote these guesses to real KNX approval."""
    result, used = [], set()
    rooms = {item['command']: item['room'] for item in preview.get('room_matches', [])
             if item.get('confidence') in ('ets_function', 'name') and item.get('room')}
    for item in preview.get("suggestions", []):
        if item.get("kind") not in KINDS or item.get("command") in used:
            continue
        result.append({key: item.get(key, "Da assegnare" if key == "room" else "")
                       for key in ("kind", "command", "name", "room")})
        if item.get('command') in rooms:
            result[-1]['room'] = rooms[item['command']]
        elif result[-1]['room'] in ('', 'Da assegnare'):
            location = building_location(preview, item['command'])
            if location:
                result[-1]['room'] = location
                result[-1]['room_source'] = 'Posizione edificio ETS dei dispositivi collegati: da verificare'
        used.update(value for value in item.values() if isinstance(value, str) and GA.fullmatch(value))
    for item in preview.get("addresses", []):
        address, dpt = item["address"], item.get("dpt", "")
        if address in used or not item.get("linked"):
            continue
        name = item.get("name", address)
        kind = None
        if re.fullmatch(r"(?:DPST-17-1|DPST-18-1|17\.001|18\.001)", dpt):
            kind = "scene"
        elif re.search(r"\b(presenza|movimento|contatto|allarme)\b", name, re.I) and dpt.startswith(("DPST-1-", "1.")):
            kind = "binary_sensor"
        elif re.search(r"\b(temperatura|umidit[aà]|lux|illuminamento|sensore)\b", name, re.I) and dpt.startswith(("DPST-9-", "DPST-14-", "9.", "14.")):
            kind = "sensor"
        elif item.get("role") == "command" and item.get("kind") in ("light", "dimmer"):
            kind = item["kind"]
        if kind:
            result.append({"kind": kind, "command": address, "name": name[:80], "room": "Da assegnare"})
            used.add(address)
    return result


def validate(payload):
    if not isinstance(payload, dict) or payload.get("mode") != "virtual_devices":
        raise ValueError("Modalità laboratorio non valida")
    project = payload.get("project", "")
    if not isinstance(project, str) or not re.fullmatch(r"[0-9a-f]{64}", project):
        raise ValueError("Progetto ETS non valido")
    devices = payload.get("devices")
    if not isinstance(devices, list) or not 1 <= len(devices) <= 200:
        raise ValueError("Seleziona da 1 a 200 dispositivi virtuali")
    result, seen = [], set()
    for item in devices:
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            raise ValueError("Tipo virtuale non supportato")
        address = item.get("command")
        if not isinstance(address, str) or not GA.fullmatch(address) or address in seen:
            raise ValueError("Indirizzo ETS non valido o duplicato")
        seen.add(address)
        name, room = item.get("name", address), item.get("room", "Da assegnare")
        for value, limit in ((name, 80), (room, 240)):
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit or any(ord(c) < 32 for c in value):
                raise ValueError("Nome o stanza non validi")
            # Template names are evaluated by HA, so reject template injection.
            if any(mark in value for mark in ("{{", "{%", "{#")):
                raise ValueError("Espressioni template non ammesse nei nomi")
        result.append({"kind": item["kind"], "command": address, "name": name.strip(), "room": room.strip()})
    return project, sorted(result, key=lambda d: tuple(map(int, d["command"].split("/"))))


def build(payload):
    project, devices = validate(payload)
    package, templates, manifest, counts = {}, {}, [], {}

    def helper(domain, key, value):
        package.setdefault(domain, {})[key] = value
        return domain + "." + key

    def action(service, entity, value=None):
        result = {"action": service, "target": {"entity_id": entity}}
        if value is not None:
            result["data"] = {"value": value}
        return result

    for device in devices:
        kind = device["kind"]
        prefix = "nm_lab_" + project[:12] + "_" + device["command"].replace("/", "_")
        name = "NM LAB " + device["name"]
        controls = []

        def number(suffix, maximum=100, initial=0, minimum=0, step=1):
            return helper("input_number", prefix + suffix, {"name": name + suffix.replace("_", " "),
                          "min": minimum, "max": maximum, "step": step, "initial": initial})

        def boolean(suffix):
            return helper("input_boolean", prefix + suffix, {"name": name + suffix.replace("_", " "), "initial": False})

        domain = {"dimmer": "light", "scene": "input_button"}.get(kind, kind)
        entity_id = domain + "." + prefix
        entity = {"name": name, "unique_id": prefix, "default_entity_id": entity_id}
        if kind in ("light", "dimmer"):
            power = boolean("_power")
            entity.update(state="{{ is_state('" + power + "', 'on') }}",
                          turn_on=[action("input_boolean.turn_on", power)],
                          turn_off=[action("input_boolean.turn_off", power)])
            if kind == "dimmer":
                level = number("_brightness", 255, 255)
                entity["level"] = "{{ states('" + level + "') | int(255) }}"
                entity["set_level"] = [action("input_number.set_value", level, "{{ brightness }}"),
                                       action("input_boolean.turn_on", power)]
        elif kind == "cover":
            position = number("_position")
            entity.update(position="{{ states('" + position + "') | int(0) }}",
                          open_cover=[action("input_number.set_value", position, 100)],
                          close_cover=[action("input_number.set_value", position, 0)],
                          set_cover_position=[action("input_number.set_value", position, "{{ position }}")],
                          stop_cover=[action("input_number.set_value", position, "{{ states('" + position + "') | int(0) }}")])
        elif kind == "scene":
            helper("input_button", prefix, {"name": name + " - richiamo simulato", "icon": "mdi:movie-open"})
        elif kind == "binary_sensor":
            source = boolean("_value")
            controls.append(source)
            entity["state"] = "{{ is_state('" + source + "', 'on') }}"
        elif kind == "sensor":
            source = number("_value", 100000, 0, -100000, 0.1)
            controls.append(source)
            entity["state"] = "{{ states('" + source + "') | float(0) }}"
        elif kind == "climate":
            heater = boolean("_heater")
            temperature = number("_temperature", 35, 20, 10, 0.5)
            controls.append(temperature)
            sensor_id = "sensor." + prefix + "_temperature"
            templates.setdefault("sensor", []).append({"name": name + " temperatura", "unique_id": prefix + "_temperature",
                "default_entity_id": sensor_id, "device_class": "temperature", "unit_of_measurement": "°C",
                "state": "{{ states('" + temperature + "') | float(20) }}"})
            # generic_thermostat derives its entity ID from name; retain a stable technical name.
            package.setdefault("climate", []).append({"platform": "generic_thermostat", "name": prefix,
                "unique_id": prefix, "heater": heater, "target_sensor": sensor_id,
                "min_temp": 15, "max_temp": 30, "target_temp": 21, "precision": 0.5, "initial_hvac_mode": "off"})
        if kind not in ("scene", "climate"):
            templates.setdefault(domain, []).append(entity)
        counts[kind] = counts.get(kind, 0) + 1
        manifest.append({**device, "entity_id": entity_id, "controls": controls})
    if templates:
        package["template"] = [templates]
    # JSON is a YAML subset, with deterministic quoting even for ETS names.
    content = json.dumps(package, ensure_ascii=False, indent=2) + "\n"
    return {"yaml": content, "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "zones": counts.get("climate", 0), "devices": len(devices), "counts": counts,
            "manifest": manifest, "project": project, "knx_traffic": False, "restart_required": True,
            "message": "Simulazione isolata: tapparelle a posizione istantanea; scene registrano solo il richiamo; sensori impostabili manualmente."}
