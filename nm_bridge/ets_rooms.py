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
    return " ".join(re.findall(r"[a-z0-9]+", value))


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
                  if item["type"] in ("Room", "Corridor", "Stairway")]
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
        haystacks = [" " + normalized(label) + " " for label in labels]
        candidates = []
        for room in room_paths:
            leaf = room.split(" / ")[-1].strip()
            needle = normalized(leaf)
            if len(needle) < 4 or needle in {"stanza", "locale", "vano", "room", "prove", "test"}:
                continue
            if any(" " + needle + " " in label for label in haystacks):
                candidates.append(room)
        if len(candidates) == 1:
            proposals.append({"command": suggestion["command"], "room": candidates[0],
                              "confidence": "name", "reason": "Nome ambiente presente nel nome/descrizione GA · da verificare"})
        else:
            proposals.append({"command": suggestion["command"], "room": "",
                              "confidence": "ambiguous" if candidates else "none",
                              "reason": "Più ambienti compatibili" if candidates else "Nessun collegamento funzionale o nome ambiente riconoscibile"})
    return proposals
