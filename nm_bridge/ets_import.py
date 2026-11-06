"""Bounded, read-only ETS group-address preview. No project data persisted."""

import io
import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET
try:
    from .ets_archive import open_project
    from .ets_rooms import extract_functions, room_matches
    from .recognition import review_suggestions, hvac_address_inventory
    from .ets_named_functions import descriptive_suggestions
except ImportError:  # The add-on runs the modules directly from /app.
    from ets_archive import open_project
    from ets_rooms import extract_functions, room_matches
    from recognition import review_suggestions, hvac_address_inventory
    from ets_named_functions import descriptive_suggestions

MAX_ARCHIVE = 16 * 1024 * 1024
MAX_XML = 12 * 1024 * 1024
MAX_TOTAL_XML = 32 * 1024 * 1024
MAX_MEMBERS = 500
MAX_ADDRESSES = 6000
MAX_OBJECT_LINKS = 20000
MAX_CATALOG_XML = 4 * 1024 * 1024
MAX_TOTAL_CATALOG = 16 * 1024 * 1024
MAX_UNLINKED_PER_DEVICE = 150
MAX_CATALOG_CANDIDATES = 120
MAX_SPACES = 400


def name_of(tag):
    return tag.rsplit("}", 1)[-1]


def extract_spaces(root):
    """Read the ETS Buildings/Locations hierarchy; physical placement is not functional control."""
    result = []

    def visit(node, parent_path, depth):
        if depth > 16 or len(result) >= MAX_SPACES:
            raise ValueError("ETS building structure exceeds safety limit")
        name = (node.get("Name") or "").strip()[:100] or "Senza nome"
        kind = (node.get("Type") or "BuildingPart")[:40]
        path = parent_path + [name]
        devices = [child.get("RefId", "")[:120] for child in node
                   if name_of(child.tag) == "DeviceInstanceRef" and child.get("RefId")]
        result.append({"name": name, "type": kind, "path": " / ".join(path),
                       "depth": depth, "devices": devices[:100]})
        for child in node:
            if name_of(child.tag) == "Space":
                visit(child, path, depth + 1)

    for locations in root.iter():
        if name_of(locations.tag) == "Locations":
            for space in locations:
                if name_of(space.tag) == "Space":
                    visit(space, [], 0)
    return result


def decode_address(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= n <= 65535:
        return None
    return f"{(n >> 11) & 31}/{(n >> 8) & 7}/{n & 255}"


def guess_kind(name, dpt):
    s = name.casefold()
    if "temperatura colore" in s or "color temperature" in s or "colour temperature" in s:
        return "dimmer"
    if any(x in s for x in ("tapparella", "venezian", "tenda", "serranda", "shutter", "blind")) or re.search(r"\b(?:movimento\s+su/giu|arresto|posizione)\s+t\d+\b", s):
        return "cover"
    if any(x in s for x in ("temperatura", "temperature", "setpoint", "clima", "termostat")):
        return "climate"
    if any(x in s for x in ("luminosit", "dimmer", "dimming")):
        return "dimmer"
    if any(x in s for x in ("luce", "luci", "lamp", "light", "led")):
        return "light"
    if dpt.startswith(("DPST-1-", "DPT-1")):
        return "binary"
    return "unknown"


LIGHT_CODE = re.compile(r"^L\s*0*[1-9][0-9]{0,2}$", re.I)
ROOM_TOKENS = ("magazzino", "ufficio", "corridoio", "ingresso", "bagno", "cucina", "sala", "salotto", "camera", "garage", "esterno", "laboratorio", "negozio", "locale tecnico")


def suggest_room(*names):
    found = {token for token in ROOM_TOKENS for name in names
             if re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", name, re.I)}
    return found.pop().title() if len(found) == 1 else "Da assegnare"


def suggest_type(base, command, feedback):
    """Infer a *draft* type from both endpoints; never assert bus semantics."""
    explicit = {x["kind"] for x in (command, feedback)} - {"unknown", "binary"}
    if len(explicit) == 1:
        kind = explicit.pop()
        return kind, "media", "Parola funzionale rilevata nel nome ETS"
    if len(explicit) > 1:
        return "unknown", "bassa", "Tipi discordanti: verifica manuale"
    if LIGHT_CODE.fullmatch(base.strip()) and re.search(r"\bon/off\b", command["name"], re.I):
        return "light", "media", "Sigla L + numero e comando ON/OFF; luce probabile, non confermata"
    if command["kind"] == "binary" or feedback["kind"] == "binary":
        return "binary", "bassa", "DPT binario: funzione non determinabile automaticamente"
    return "unknown", "bassa", "Nome e DPT non sufficienti"


def guess_role(name):
    s = name.casefold()
    if re.search(r"\b(stato|status|feedback|riscontro)\b", s):
        return "feedback"
    if re.search(r"\b(comando|cmd|command|on/off|accensione)\b", s):
        return "command"
    return "unknown"


def base_name(name):
    stem = re.sub(r"\b(notifica|stato|status|feedback|riscontro|comando|cmd|command|on/off|accensione)\b", " ", name.casefold())
    stem = re.sub(r"\s+", " ", stem).strip(" -_ ")
    # Some ETS projects call actuator feedback "STATO LED L5" while the
    # corresponding command is "ON/OFF L5". Only remove this exact prefix
    # for a numbered lighting channel, not for arbitrary LED controls.
    if re.fullmatch(r"led\s+l\d{1,3}", stem):
        return stem.split()[-1]
    return stem


def structured_suggestions(items):
    """Infer whole functions from a consistent ETS circuit group, not its mnemonic.

    Requires unambiguous role/DPT combinations and linked GAs. A token like
    L03, T01 or Z01 is only a grouping key, never proof of an entity type.
    """
    groups = {}
    for item in items:
        parts = [p.strip() for p in item.get("name", "").split(" - ")]
        if len(parts) < 2 or not item.get("linked"):
            continue
        space, circuit, role = (parts[0], parts[1], " - ".join(parts[2:]).casefold()) if len(parts) >= 3 else ("Da assegnare", parts[0], parts[1].casefold())
        if not space or not circuit or not role:
            continue
        groups.setdefault((space, circuit), []).append((item, role))

    proposals, consumed = [], set()
    def dpt(item):
        raw = (item.get("dpt") or "").upper()
        m = re.fullmatch(r"(?:DPST-|DPT-)?(\d+)[.-](\d+)", raw)
        return f"{int(m[1])}.{int(m[2]):03d}" if m else ""

    for (space, circuit), entries in groups.items():
        def one(pattern, types):
            matches = [item for item, role in entries
                       if re.search(pattern, role) and dpt(item) in types]
            return matches[0]["address"] if len(matches) == 1 else None

        light_on = one(r"^(?:comando\s+)?on\s*/\s*off(?:\s+comando)?$", {"1.001"})
        light_fb = one(r"^(?:on\s*/\s*off\s+(?:feedback|stato)|(?:stato|feedback)(?:\s+on\s*/\s*off)?)$", {"1.001", "1.011"})
        brightness = one(r"luminosit[aà]\s+comando", {"5.001"})
        brightness_fb = one(r"luminosit[aà]\s+feedback", {"5.001"})
        relative = one(r"dimmer\s+relativ|regolazione\s+relativ", {"3.007"})
        cct = one(r"temperatura\s+colore\s+comando", {"7.600"})
        cct_fb = one(r"temperatura\s+colore\s+feedback", {"7.600"})

        move = one(r"^(?:movimento(?:\s+comando)?|(?:comando\s+)?(?:su\s*/\s*gi[uù]|salita\s*/\s*discesa)(?:\s+comando)?)$", {"1.008"})
        stop = one(r"^(?:comando\s+)?(?:step\s*/?\s*stop|stop|arresto)(?:\s+comando)?$", {"1.007", "1.017"})
        position = one(r"^posizione\s+comando$", {"5.001"})
        position_fb = one(r"^posizione\s+feedback$", {"5.001"})
        slats = one(r"lamelle\s+comando", {"5.001"})
        slats_fb = one(r"lamelle\s+feedback", {"5.001"})

        ambient = one(r"^temperatura\s+ambiente$", {"9.001"})
        setpoint = one(r"^setpoint\s+comando$", {"9.001"})
        setpoint_fb = one(r"^setpoint\s+(?:corrente|stato|feedback)$", {"9.001"})
        humidity = one(r"^umidit[aà]\s+ambiente$", {"9.007", "5.001"})
        mode = one(r"^hvac\s+comando$", {"20.102"})
        mode_fb = one(r"^hvac\s+feedback$", {"20.102"})
        heat = one(r"^riscaldamento\s+comando$", {"1.001"})
        valve_fb = one(r"^valvola\s+stato$", {"1.011", "1.001"})

        fields = {}
        kind = None
        if light_on and not (move or ambient or setpoint):
            kind = "dimmer" if brightness or relative else "light"
            fields = {"command": light_on, "feedback": light_fb}
            if kind == "dimmer":
                fields.update({"brightness": brightness, "brightness_feedback": brightness_fb})
                if relative:
                    fields["relative"] = relative
                if cct and cct_fb:
                    fields.update({"color_temperature": cct, "color_temperature_feedback": cct_fb})
        elif move and stop and not (light_on or ambient or setpoint):
            kind = "cover"
            fields = {"command": move, "stop": stop}
            if position and position_fb:
                fields.update({"position": position, "position_feedback": position_fb})
            if slats and slats_fb:
                fields.update({"slats": slats, "slats_feedback": slats_fb})
        elif ambient and setpoint and setpoint_fb and not (light_on or move):
            kind = "climate"
            fields = {"command": setpoint, "temperature": ambient,
                      "target_temperature_state": setpoint_fb}
            for key, value in (("humidity", humidity), ("operation_mode", mode),
                               ("operation_mode_state", mode_fb), ("heating_demand", heat),
                               ("valve_state", valve_fb)):
                if value:
                    fields[key] = value
        if not kind:
            continue
        fields = {k: v for k, v in fields.items() if v}
        proposals.append({"name": circuit if space == "Da assegnare" else f"{space} - {circuit}", "kind": kind, **fields,
                          "room": space, "confidence": "media",
                          "reason": "Ruoli di circuito e DPT coerenti; verificare direzione e oggetti ETS"})
        consumed.update(fields.values())
    return proposals, consumed


def cover_suggestions(items, used_commands):
    """Recognize a cover's distinct movement/stop/position objects as a draft."""
    groups = {}
    for item in items:
        match = re.search(r"\bT\s*(\d{1,3})\b", item["name"], re.I)
        if not match:
            continue
        tag = "T" + str(int(match.group(1)))
        label = item["name"].casefold()
        role = ("move" if re.search(r"movimento\s+su\s*/\s*giu|\b(up/down|su/giu)\b", label)
                else "stop" if "arresto" in label or "stop" in label
                else "position" if "posizione" in label or "position" in label else None)
        if role:
            groups.setdefault(tag, {}).setdefault(role, []).append(item)
    result = []
    for tag, parts in groups.items():
        movement = parts.get("move", [])
        if len(movement) != 1 or movement[0]["address"] in used_commands or not movement[0]["linked"]:
            continue
        stop = parts.get("stop", [])
        position = parts.get("position", [])
        source = movement + stop + position
        linked_position = position[0] if len(position) == 1 and position[0]["linked"] else None
        result.append({"name": tag, "kind": "cover", "command": movement[0]["address"],
                       "feedback": None, "stop": stop[0]["address"] if len(stop) == 1 and stop[0]["linked"] else None,
                       "position": linked_position["address"] if linked_position else None,
                       "room": suggest_room(*(x["name"] for x in source), *(x["description"] for x in source)),
                       "confidence": "media" if len(stop) == 1 else "bassa",
                       "reason": ("Movimento SU/GIU identificato; l'indirizzo posizione " + position[0]["address"] +
                                  " NON è collegato nel file ETS: lasciato vuoto" if len(position) == 1 and not linked_position
                                  else "Movimento SU/GIU identificato; verifica funzione e DPT di arresto/posizione")})
        for item in source:
            item["kind"] = "cover"
    return result


def dimmer_fields(items, suggestions):
    """Suggest auxiliary dimmer GAs only for an unambiguous numbered channel."""
    for proposal in suggestions:
        if proposal["kind"] != "dimmer":
            continue
        match = re.search(r"\bL\s*0*(\d{1,3})\b", proposal["name"], re.I)
        if not match:
            continue
        channel = int(match.group(1))
        related = [item for item in items if item["linked"] and
                   (m := re.search(r"\bL\s*0*(\d{1,3})\b", item["name"], re.I)) and
                   int(m.group(1)) == channel]
        patterns = {
            "relative": r"regolazion|incrementa|decrementa|dimming",
            "brightness": r"valore\s+luminosit.*(?:via\s+bus|comando)|comando\s+valore",
            "brightness_feedback": r"(?:valore\s+luminosit.*(?:corrente|attuale)|stato\s+luminosit)",
        }
        for field, pattern in patterns.items():
            hits = [item for item in related if re.search(pattern, item["name"], re.I)]
            if len(hits) == 1 and hits[0]["address"] not in (proposal["command"], proposal["feedback"]):
                proposal[field] = hits[0]["address"]


def climate_suggestions(items, used_commands, existing=None):
    """Conservative room-qualified thermostat drafts: never infer HVAC from temperature alone."""
    groups = {}
    for item in items:
        if not item["linked"]:
            continue
        name = item["name"].casefold()
        match = re.match(r"^(?:termostato|clima|hvac)\s+(.+?)\s*[-:]\s*(.+)$", name)
        if not match:
            continue
        room, function = match.groups()
        role = ("temperature" if re.search(r"temperatura\s+(?:ambiente|attuale|misurata)", function)
                else "target_temperature" if re.search(r"(?:setpoint|temperatura\s+desiderata|temperatura\s+impostata)\s*(?:comando)?", function) and not re.search(r"stato|feedback", function)
                else "target_temperature_state" if re.search(r"(?:setpoint|temperatura\s+desiderata).*?(?:stato|feedback)", function)
                else "heat_cool" if re.search(r"(?:estate\s*/\s*inverno|riscaldamento\s*/\s*raffrescamento|heat\s*/\s*cool)", function) and not re.search(r"stato|feedback", function)
                else "heat_cool_state" if re.search(r"(?:estate\s*/\s*inverno|riscaldamento\s*/\s*raffrescamento|heat\s*/\s*cool).*?(?:stato|feedback)", function)
                else "operation_mode" if re.search(r"modalit[aà].*(?:comando|operativ)", function) and not re.search(r"stato|feedback", function)
                else "operation_mode_state" if re.search(r"modalit[aà].*(?:stato|feedback)", function)
                else None)
        if role:
            groups.setdefault(room.strip(), {}).setdefault(role, []).append(item)
    results = []
    for room, roles in groups.items():
        if len(roles.get("target_temperature", [])) != 1 or len(roles.get("temperature", [])) != 1:
            continue
        command = roles["target_temperature"][0]["address"]
        if command in used_commands and not any(p["command"] == command and p["kind"] == "climate"
                                             for p in (existing or [])):
            continue
        proposal = {"name": "TERMOSTATO " + room.upper(), "kind": "climate", "command": command,
                    "feedback": None, "temperature": roles["temperature"][0]["address"],
                    "room": suggest_room(room), "confidence": "bassa",
                    "reason": "Setpoint e temperatura ambiente distinti; confermare DPT 9.001 e modalità HVAC in ETS"}
        for field in ("target_temperature_state", "heat_cool", "heat_cool_state", "operation_mode", "operation_mode_state"):
            if len(roles.get(field, [])) == 1:
                proposal[field] = roles[field][0]["address"]
        matched = next((p for p in (existing or []) if p["command"] == command and p["kind"] == "climate"), None)
        if matched:
            matched.update({key: value for key, value in proposal.items() if key not in ("name", "kind", "command")})
        else:
            results.append(proposal)
    return results


def climate_zone_suggestions(items, used_commands):
    """Recognize a repeated thermostat GA block without requiring a room mnemonic.

    Each ETS middle group must contain unique, linked ambient, manual target,
    current target and HVAC mode fields with the right DPT. Their common middle
    address is evidence of a functional cluster, NOT an assertion of room.
    """
    groups = {}
    for item in items:
        if not item.get("linked"):
            continue
        address = item.get("address", "")
        if not re.fullmatch(r"\d+/\d+/\d+", address):
            continue
        groups.setdefault(address.rsplit("/", 1)[0], []).append(item)

    roles = (
        ("temperature", r"^temperatura\s+ambiente\b", "DPST-9-1"),
        ("command", r"^setpoint\s+manuale\b", "DPST-9-1"),
        ("target_temperature_state", r"^setpoint\s+attuale\b", "DPST-9-1"),
        ("operation_mode", r"^modo\s+hvac\s+in\b", "DPST-20-102"),
        ("operation_mode_state", r"^modo\s+hvac\s+stato\b", "DPST-20-102"),
        ("heat_cool", r"^estate\s+inverno\s+in\b", "DPST-1-100"),
        ("heat_cool_state", r"^estate\s+inverno\s+out\b", "DPST-1-100"),
    )
    proposals = []
    for group, addresses in groups.items():
        found = {}
        for field, pattern, dpt in roles:
            matched = [a for a in addresses if re.search(pattern, a.get("name", ""), re.I)
                       and a.get("dpt", "").upper() == dpt]
            if len(matched) == 1:
                found[field] = matched[0]["address"]
            elif len(matched) > 1:
                found[field] = None  # Ambiguous role must block the proposal.
        mandatory = ("temperature", "command", "target_temperature_state",
                     "operation_mode", "operation_mode_state")
        if any(not found.get(key) for key in mandatory) or found["command"] in used_commands:
            continue
        # Only a true named input is a command; never turn an unlinked GA into one.
        # An individual thermostat need not have its own writable season object.
        source = next(a for a in addresses if a["address"] == found["temperature"])
        suffix = re.sub(r"^temperatura\s+ambiente\b", "", source["name"], flags=re.I).strip()
        label = suffix.upper() if suffix else group.replace("/", "-")
        proposal = {"name": "TERMOSTATO " + label, "kind": "climate",
                    **{key: value for key, value in found.items() if value},
                    "room": "Da assegnare", "confidence": "media",
                    "reason": "Blocco HVAC ETS coerente per DPT e gruppo; ambiente e direzioni da verificare"}
        proposals.append(proposal)
    return proposals


def channel_suggestions(items, used_commands):
    """Infer standard ETS channel naming without assuming a manufacturer's brand.

    Recognizes `CH-2 - Dimming : OnOff` independently of language-specific
    installer aliases such as L2 or T2. All suggestions remain unapproved.
    """
    groups = {}
    for item in items:
        if not item["linked"]:
            continue
        match = re.match(r"^CH\s*[- ]\s*(\d{1,3})\s*[-:]\s*(.+?)\s*:\s*(.+)$", item["name"], re.I)
        if not match:
            continue
        channel, label, action = match.groups()
        family = ("cover" if re.search(r"blind|shutter|tapparel|venezian", label, re.I)
                  else "dimmer" if re.search(r"dimm|regolaz", label, re.I)
                  else "light" if re.search(r"switch|commut|on/off", label, re.I) else None)
        if family:
            groups.setdefault((int(channel), family), []).append((item, action.casefold()))
    result = []
    for (channel, family), group in groups.items():
        def matched(pattern):
            return [item for item, action in group if re.search(pattern, action)]
        command = ([item for item, action in group if re.search(r"\bon\s*/?\s*off\b|\bonoff\b", action)
                    and not re.search(r"feedback|status|stato", action)] if family != "cover"
                   else matched(r"\bmove\b|\bup\s*/\s*down\b"))
        # A command must be unambiguous and match the expected KNX DPT class.
        expected = "DPST-1-8" if family == "cover" else "DPST-1-1"
        command = [item for item in command if item.get("dpt", "").upper() in (expected, "")]
        if len(command) != 1 or command[0]["address"] in used_commands:
            continue
        feedback = matched(r"feedback|status|stato")
        if family == "cover":
            stop = matched(r"step\s*/\s*stop|\bstop\b|arresto")
            position = [item for item in feedback if item.get("dpt", "").upper() in ("DPST-5-1", "DPT-5.001")]
            proposal = {"name": f"CH{channel} TAPPARELLA", "kind": "cover",
                        "command": command[0]["address"], "feedback": None,
                        "stop": stop[0]["address"] if len(stop) == 1 else None,
                        "position": None, "room": "Da assegnare", "confidence": "media",
                        "reason": "Canale ETS + DPT di movimento/stop; il feedback posizione resta da verificare"}
            if len(position) == 1:
                proposal["position_feedback_suggestion"] = position[0]["address"]
        else:
            feedback = [item for item in feedback if re.search(r"on\s*/?\s*off|onoff|feedback", item["name"], re.I)]
            proposal = {"name": f"CH{channel} {'DIMMER' if family == 'dimmer' else 'LUCE'}",
                        "kind": family, "command": command[0]["address"],
                        "feedback": feedback[0]["address"] if len(feedback) == 1 else None,
                        "room": "Da assegnare", "confidence": "media",
                        "reason": "Canale ETS e funzione riconoscibili; associazioni da verificare"}
            if family == "dimmer":
                relative = matched(r"dimming\s+control|regolaz|dimming\s+relative")
                if len(relative) == 1 and relative[0].get("dpt", "").upper() in ("DPST-3-7", "DPT-3.007", ""):
                    proposal["relative"] = relative[0]["address"]
        result.append(proposal)
    return result


def application_file(device):
    """Locate one manufacturer application from a project's hardware reference."""
    ref = device.get("Hardware2ProgramRefId", "")
    if "_HP-" not in ref:
        return None
    maker, program = ref.split("_HP-", 1)
    maker = maker.split("_", 1)[0]
    if not re.fullmatch(r"M-[0-9A-Fa-f]{4}", maker) or not re.fullmatch(r"[0-9A-Fa-f-]{3,90}", program):
        return None
    return f"{maker}/{maker}_A-{program}.xml"


def catalog_key(reference):
    """Keep module definitions; remove only application and instance prefixes."""
    return '_'.join(p for p in reference.split('_') if p.startswith(('MD-', 'O-', 'R-')))


def catalog_objects(archive, filename, cache, budget):
    if not filename:
        return {}
    if filename in cache:
        return cache[filename]
    try:
        info = archive.getinfo(filename)
    except KeyError:
        return {}
    if info.file_size > MAX_CATALOG_XML or budget[0] + info.file_size > MAX_TOTAL_CATALOG or info.flag_bits & 1:
        return {}
    budget[0] += info.file_size
    content = archive.read(info)
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        return {}
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {}
    objects = {}
    for node in root.iter():
        if name_of(node.tag) != "ComObject":
            continue
        obj_id = catalog_key(node.get("Id") or "")
        if obj_id and len(objects) < MAX_OBJECT_LINKS:
            objects[obj_id] = {"name": (node.get("Name") or "")[:120],
                               "function": (node.get("FunctionText") or "")[:100],
                               "number": node.get("Number"),
                               "size": (node.get("ObjectSize") or "")[:32],
                               "dpt": (node.get("DatapointType") or "")[:100],
                               "flags": {k: node.get(k) == "Enabled" for k in (
                                   "CommunicationFlag", "ReadFlag", "WriteFlag", "TransmitFlag", "UpdateFlag")}}
    # Parameter-specific ComObjectRef values override generic ComObject
    # metadata (critical for multi-function input channels).
    for node in root.iter():
        if name_of(node.tag) != "ComObjectRef":
            continue
        ref_key = (node.get("Id") or "").split("_O-", 1)
        if len(ref_key) != 2 or "_R-" not in ref_key[1]:
            continue
        key = catalog_key(node.get("Id") or "")
        base = objects.get(key.split("_R-", 1)[0], {})
        objects[key] = {**base,
                        "name": (node.get("Text") or node.get("Name") or base.get("name") or "")[:120],
                        "function": (node.get("FunctionText") or base.get("function") or "")[:100],
                        "size": (node.get("ObjectSize") or base.get("size") or "")[:32],
                        "dpt": (node.get("DatapointType") or base.get("dpt") or "")[:100],
                        "flags": {**base.get('flags', {}), **{k: node.get(k) == 'Enabled'
                                  for k in ('CommunicationFlag', 'ReadFlag', 'WriteFlag', 'TransmitFlag', 'UpdateFlag')
                                  if node.get(k) is not None}},
                        "source": "riferimento applicativo"}
    cache[filename] = objects
    return objects


def preview(raw, password=""):
    if len(raw) > MAX_ARCHIVE or len(raw) < 4:
        raise ValueError("Project file too large or empty")
    with open_project(raw, password, MAX_MEMBERS, MAX_XML, MAX_TOTAL_XML) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Too many archive entries")
        # Use a stable project GUID so review notes survive new exports of
        # the same ETS project. Never expose or persist the original GUID.
        project_key = hashlib.sha256(raw).hexdigest()
        for info in members:
            if info.filename.lower().endswith('/project.xml') and info.file_size <= 128 * 1024:
                content = archive.read(info)
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    continue
                try:
                    metadata = ET.fromstring(content)
                except ET.ParseError:
                    continue
                for elem in metadata.iter():
                    if name_of(elem.tag) == "ProjectInformation" and re.fullmatch(
                            r"[0-9a-fA-F-]{36}", elem.get("Guid", "")):
                        project_key = hashlib.sha256(elem.get("Guid").lower().encode()).hexdigest()
                        break
                break
        xmls = []
        total = 0
        for info in members:
            # ETS embeds manufacturer/application catalogues under M-*.
            # Those can be much larger than the installation XML and are not
            # needed for the group-address inventory. Inspect P-* only.
            if info.is_dir() or not info.filename.lower().endswith(".xml") or not info.filename.lower().startswith("p-"):
                continue
            if info.flag_bits & 1:
                raise ValueError("Password-protected projects are not supported")
            if info.file_size > MAX_XML:
                raise ValueError("Project XML too large")
            total += info.file_size
            if total > MAX_TOTAL_XML:
                raise ValueError("Project exceeds XML safety limit")
            xmls.append(info)
        addresses = {}
        link_count = 0
        app_cache = {}
        catalog_budget = [0]
        device_inventory = []
        building_spaces = []
        function_refs = []
        address_refs = {}
        for info in xmls:
            # Read only declared XML members, without extracting archive paths.
            content = archive.read(info)
            if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                raise ValueError("XML entities are not allowed")
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                continue
            building_spaces.extend(extract_spaces(root))
            function_refs.extend(extract_functions(root))
            if len(building_spaces) > MAX_SPACES:
                raise ValueError("Too many ETS building spaces")
            local_addresses = {}
            for node in root.iter():
                if name_of(node.tag) != "GroupAddress":
                    continue
                group = decode_address(node.get("Address"))
                if group is None:
                    continue
                name = (node.get("Name") or "").strip()[:160]
                dpt = (node.get("DPTs") or node.get("DatapointType") or "").strip()[:100]
                description = (node.get("Description") or "").strip()[:250]
                record = {"address": group, "name": name, "description": description,
                          "dpt": dpt, "kind": guess_kind(name, dpt), "role": guess_role(name),
                          "linked": False, "connections": []}
                addresses[group] = record
                if node.get("Id"):
                    address_refs[node.get("Id")] = group
                    local_addresses[node.get("Id").rsplit("_", 1)[-1]] = record
                if len(addresses) > MAX_ADDRESSES:
                    raise ValueError("Too many group addresses")
            # Links on ComObjectInstanceRef are a direct project-level
            # association, unlike names or DPT guesses. Preserve only a small,
            # bounded inventory per GA; do not load manufacturer catalogues.
            for device in root.iter():
                if name_of(device.tag) != "DeviceInstance":
                    continue
                dev_label = (device.get("Description") or device.get("Name") or "Dispositivo").strip()[:100]
                program_file = application_file(device)
                objects = catalog_objects(archive, program_file, app_cache, catalog_budget)
                device_id = f"device-{len(device_inventory) + 1}"
                device_inventory.append({"id": device_id, "name": dev_label, "address_suffix": device.get("Address"),
                                         "ets_id": (device.get("Id") or "")[:120],
                                         "product_ref": (device.get("ProductRefId") or "")[:140],
                                         "program": program_file or "", "catalog_read": bool(objects),
                                         "connected_objects": 0, "linked_addresses": 0,
                                         "unlinked_objects": [], "unlinked_count": 0,
                                         "catalog_candidates": [], "catalog_candidates_count": 0})
                if len(device_inventory) > 1000:
                    raise ValueError("Too many devices")
                instance_refs = set()
                for obj in device.iter():
                    if name_of(obj.tag) != "ComObjectInstanceRef":
                        continue
                    instance_refs.add(catalog_key(obj.get("RefId") or "").split("_R-", 1)[0])
                    refs = (obj.get("Links") or "").split()
                    if refs:
                        device_inventory[-1]["connected_objects"] += 1
                    else:
                        device_inventory[-1]["unlinked_count"] += 1
                        if len(device_inventory[-1]["unlinked_objects"]) < MAX_UNLINKED_PER_DEVICE:
                            ref_id = (obj.get("RefId") or "")[:100]
                            details = objects.get(catalog_key(ref_id), {})
                            device_inventory[-1]["unlinked_objects"].append({"object_ref": ref_id, **details})
                    link_count += len(refs)
                    if link_count > MAX_OBJECT_LINKS:
                        raise ValueError("Too many KNX object links")
                    for ref in refs:
                        record = local_addresses.get(ref)
                        if record is not None:
                            record["linked"] = True
                            device_inventory[-1]["linked_addresses"] += 1
                            if len(record["connections"]) < 12:
                                ref_id = (obj.get("RefId") or "")[:100]
                                details = objects.get(catalog_key(ref_id), {})
                                record["connections"].append({"device_id": device_id, "device": dev_label,
                                                              "object_ref": ref_id, **details})
                # The manufacturer's catalogue can contain objects disabled by
                # ETS parameters. These are POSSIBILITIES, never asserted to be
                # active or missing in the installed device.
                candidates = [(key, val) for key, val in objects.items()
                              if "_R-" not in key and key not in instance_refs]
                device_inventory[-1]["catalog_candidates_count"] = len(candidates)
                device_inventory[-1]["catalog_candidates"] = [
                    {"object_ref": key, **val} for key, val in candidates[:MAX_CATALOG_CANDIDATES]
                ]
        if not addresses:
            raise ValueError("No group addresses found (check ETS project format)")
        items = sorted(addresses.values(), key=lambda x: tuple(map(int, x["address"].split("/"))))
        by_name = {}
        for item in items:
            if item["role"] in ("command", "feedback"):
                key = base_name(item["name"])
                if key:
                    by_name.setdefault(key, {}).setdefault(item["role"], []).append(item)
        suggestions = []
        for base, parts in by_name.items():
            if len(parts.get("command", [])) == 1 and len(parts.get("feedback", [])) == 1:
                cmd, fb = parts["command"][0], parts["feedback"][0]
                kind, confidence, reason = suggest_type(base, cmd, fb)
                suggestions.append({"name": base.upper(), "kind": kind,
                                    "command": cmd["address"], "feedback": fb["address"],
                                    "room": suggest_room(cmd["name"], fb["name"], cmd["description"], fb["description"]),
                                    "confidence": confidence, "reason": reason})
                # Propagate inference into the address inventory as a *suggestion*.
                if kind != "unknown":
                    for endpoint in (cmd, fb):
                        if endpoint["kind"] in ("unknown", "binary"):
                            endpoint["kind"] = kind
        suggestions.extend(cover_suggestions(items, {x["command"] for x in suggestions}))
        suggestions.extend(climate_suggestions(items, {x["command"] for x in suggestions}, suggestions))
        suggestions.extend(climate_zone_suggestions(items, {x["command"] for x in suggestions}))
        suggestions.extend(channel_suggestions(items, {x["command"] for x in suggestions}))
        dimmer_fields(items, suggestions)
        structured, covered_addresses = structured_suggestions(items)
        suggestions = [s for s in suggestions if s["command"] not in covered_addresses]
        suggestions.extend(structured)
        descriptive, covered_addresses = descriptive_suggestions(items)
        suggestions = [s for s in suggestions if s['command'] not in covered_addresses]
        suggestions.extend(descriptive)
        suggestions.sort(key=lambda x: tuple(map(int, x["command"].split("/"))))
        functions = [{"name": item["name"], "space": item["space"],
                      "addresses": list(dict.fromkeys(address_refs[ref] for ref in item["refs"] if ref in address_refs))}
                     for item in function_refs]
        matches = room_matches(suggestions[:300], items, building_spaces, functions)
        return {"project_key": project_key, "addresses": items, "devices": device_inventory, "suggestions": suggestions[:300],
                "recognition_reviews": review_suggestions(items, suggestions),
                "hvac_inventory": hvac_address_inventory(items),
                "building": building_spaces, "functions": functions, "room_matches": matches, "total": len(items),
                "warning": "Tipi e abbinamenti sono ipotesi, non verifiche ETS. DPT mancanti da controllare. Nessun dato salvato."}

