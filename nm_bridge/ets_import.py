"""Bounded, read-only ETS group-address preview. No project data persisted."""

import io
import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET
try:
    from .ets_rooms import extract_functions, room_matches
except ImportError:  # The add-on runs the modules directly from /app.
    from ets_rooms import extract_functions, room_matches

MAX_ARCHIVE = 8 * 1024 * 1024
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
    return re.sub(r"\s+", " ", stem).strip(" -_ ")


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
        obj_id = (node.get("Id") or "").rsplit("_", 1)[-1]
        if obj_id.startswith("O-") and len(objects) < MAX_OBJECT_LINKS:
            objects[obj_id] = {"name": (node.get("Name") or "")[:120],
                               "function": (node.get("FunctionText") or "")[:100],
                               "number": node.get("Number"),
                               "size": (node.get("ObjectSize") or "")[:32],
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
        key = "O-" + ref_key[1]
        base = objects.get(key.split("_R-", 1)[0], {})
        objects[key] = {**base,
                        "name": (node.get("Text") or node.get("Name") or base.get("name") or "")[:120],
                        "function": (node.get("FunctionText") or base.get("function") or "")[:100],
                        "size": (node.get("ObjectSize") or base.get("size") or "")[:32],
                        "source": "riferimento applicativo"}
    cache[filename] = objects
    return objects


def preview(raw):
    if len(raw) > MAX_ARCHIVE or len(raw) < 4:
        raise ValueError("Project file too large or empty")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Not a valid unencrypted .knxproj archive") from exc
    with archive:
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
                    instance_refs.add((obj.get("RefId") or "").split("_R-", 1)[0])
                    refs = (obj.get("Links") or "").split()
                    if refs:
                        device_inventory[-1]["connected_objects"] += 1
                    else:
                        device_inventory[-1]["unlinked_count"] += 1
                        if len(device_inventory[-1]["unlinked_objects"]) < MAX_UNLINKED_PER_DEVICE:
                            ref_id = (obj.get("RefId") or "")[:100]
                            details = objects.get(ref_id, {})
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
                                details = objects.get(ref_id, {})
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
        suggestions.sort(key=lambda x: tuple(map(int, x["command"].split("/"))))
        functions = [{"name": item["name"], "space": item["space"],
                      "addresses": list(dict.fromkeys(address_refs[ref] for ref in item["refs"] if ref in address_refs))}
                     for item in function_refs]
        matches = room_matches(suggestions[:300], items, building_spaces, functions)
        return {"project_key": project_key, "addresses": items, "devices": device_inventory, "suggestions": suggestions[:300],
                "building": building_spaces, "functions": functions, "room_matches": matches, "total": len(items),
                "warning": "Tipi e abbinamenti sono ipotesi, non verifiche ETS. DPT mancanti da controllare. Nessun dato salvato."}
