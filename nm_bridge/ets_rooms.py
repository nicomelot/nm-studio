"""Room proposals from explicit ETS functions or conservative name evidence.

No bus access. Physical device location is deliberately NOT used to infer
the functional room controlled by a group address.
"""

import re
import unicodedata


MAX_FUNCTIONS = 1000
MAX_ROOM_MATCHES = 300


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def normalized(text):
    value = unicodedata.normalize("NFKD", str(text).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    words = re.findall(r"[a-z0-9]+", value)
    return " ".join({'interr': 'interrato'}.get(word, word) for word in words
                    if word not in {'di', 'da', 'del', 'della', 'delle', 'dei'})


def extract_functions(root):
    """Record Function -> GroupAddressRef relationships under room Spaces."""
    result = []

    def inspect(space, path):
        name = (space.get("Name") or "").strip()[:100]
        current = path + [name]
        for child in space:
            tag = local_name(child.tag)
            if tag == "Space":
                inspect(child, current)
            elif tag == "Function":
                collect(child, current)

    def collect(function, path):
        if len(result) >= MAX_FUNCTIONS:
            raise ValueError("Too many ETS building functions")
        refs = [node.get("RefId", "")[:120] for node in function.iter()
                if local_name(node.tag) == "GroupAddressRef" and node.get("RefId")]
        result.append({"name": (function.get("Name") or "").strip()[:100],
                       "space": " / ".join(path), "refs": refs[:100]})
        for child in function:
            if local_name(child.tag) == "Function":
                collect(child, path)

    for locations in root.iter():
        if local_name(locations.tag) == "Locations":
            for child in locations:
                if local_name(child.tag) == "Space":
                    inspect(child, [])
    return result


def room_matches(suggestions, addresses, spaces, functions):
    """Return reviewable proposals; ties and weak matches stay unassigned."""
    room_paths = [item["path"] for item in spaces
                  if item.get("type") in ("Room", "Corridor", "Stairway")]
    lookup = {item["address"]: item for item in addresses}
    proposals = []
    for suggestion in suggestions[:MAX_ROOM_MATCHES]:
        used_addresses = {suggestion.get(field) for field in ("command", "feedback", "stop", "position")}
        linked = {func["space"] for func in functions
                  if func["space"] in room_paths and used_addresses.intersection(func.get("addresses", []))}
        if len(linked) == 1:
            room = next(iter(linked))
            proposals.append({"command": suggestion["command"], "room": room,
                              "confidence": "ets_function", "reason": "Funzione edificio ETS collegata al GA"})
            continue
        if len(linked) > 1:
            proposals.append({"command": suggestion["command"], "room": "",
                              "confidence": "ambiguous", "reason": "Più funzioni ETS in ambienti diversi"})
            continue

        labels = [suggestion.get("name", "")]
        for address in used_addresses:
            record = lookup.get(address)
            if record:
                labels.extend([record.get("name", ""), record.get("description", "")])
        haystacks = [' ' + normalized(label) + ' ' for label in labels]
        candidates = []
        for room in dict.fromkeys(room_paths):
            parts = room.split(' / ')
            leaf = normalized(parts[-1])
            aliases = {leaf}
            # ETS often repeats the floor in room names: Bagno PIANO TERRA.
            if len(parts) >= 3:
                floor = normalized(parts[-2])
                for suffix in {floor, floor.removeprefix('piano ')}:
                    if suffix and leaf.endswith(' ' + suffix):
                        aliases.add(leaf[:-len(suffix)].strip())
            matches = [alias for alias in aliases if len(alias) >= 4
                       and alias not in {'stanza', 'locale', 'vano', 'room', 'prove', 'test'}
                       and any(' ' + alias + ' ' in label for label in haystacks)]
            if matches:
                candidates.append(room)
        # Prefer the most specific room name (Bagno ospiti over Bagno),
        # but never break ties using iteration order or device addresses.
        if len(candidates) > 1:
            explicit = [room for room in candidates
                        if any(' ' + normalized(room.split(' / ')[-1]) + ' ' in h for h in haystacks)]
            if explicit:
                candidates = [room for room in candidates if not any(
                    normalized(room.split(' / ')[-1]) != normalized(other.split(' / ')[-1])
                    and ' ' + normalized(room.split(' / ')[-1]) + ' ' in ' ' + normalized(other.split(' / ')[-1]) + ' '
                    for other in explicit)]
        if len(candidates) > 1:
            by_floor = [room for room in candidates if len(room.split(' / ')) >= 3
                        and any(' ' + alias + ' ' in h for alias in {normalized(room.split(' / ')[-2]), normalized(room.split(' / ')[-2]).removeprefix('piano ')} if alias for h in haystacks)]
            if by_floor:
                candidates = by_floor
        if len(candidates) == 1:
            proposals.append({"command": suggestion["command"], "room": candidates[0],
                              "confidence": "name", "reason": "Nome ambiente presente nel nome/descrizione GA · da verificare"})
        else:
            proposals.append({"command": suggestion["command"], "room": "",
                              "confidence": "ambiguous" if candidates else "none",
                              "reason": "Più ambienti compatibili" if candidates else "Nessun collegamento funzionale o nome ambiente riconoscibile"})
    return proposals

