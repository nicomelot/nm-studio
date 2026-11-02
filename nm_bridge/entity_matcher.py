"""Read-only suggestions for linking reviewed KNX widgets to HA entities."""

import re
import unicodedata


COMPATIBLE = {"light": {"light", "switch"}, "dimmer": {"light"}, "cover": {"cover"}}
STOP = {"luce", "luci", "stato", "comando", "on", "off", "knx", "ha", "di", "del", "della", "il", "la", "le", "the"}
FEEDBACK_WORDS = {"notifica", "feedback", "riscontro", "segnalazione", "status"}
UNCERTAIN_WORDS = {"pulsantiera", "pulsante", "scatola", "derivazione"}


def classify_entity(entity):
    """Conservative naming hints, not proof of KNX group-address roles."""
    value = " ".join((str(entity.get("name") or ""), str(entity.get("entity_id") or "").replace("_", " ")))
    words = set(tokens(value))
    # 'stato' alone can be part of an ordinary label; paired with a notification
    # strongly suggests a separate feedback object rather than a command.
    if words & FEEDBACK_WORDS or ("stato" in value.lower() and "notifica" in value.lower()):
        return "feedback_probabile"
    if words & UNCERTAIN_WORDS:
        return "da_verificare"
    return "funzione_candidata"


def tokens(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(c for c in normalized if not unicodedata.combining(c)).lower()
    return [t for t in re.findall(r"[a-z]+\d*|\d+", normalized) if t not in STOP]


def suggest(layout, entities):
    """Suggestions only: no persistent changes, services or KNX requests."""
    widgets = layout.get("widgets", [])
    indexed = {e.get("entity_id"): e for e in entities if isinstance(e, dict) and isinstance(e.get("entity_id"), str)}
    used = {w.get("entity_id") for w in widgets if w.get("entity_id")}
    proposed = set()
    proposals = []
    for index, widget in enumerate(widgets):
        current = widget.get("entity_id", "")
        widget_tokens = set(tokens(widget.get("name", "")))
        room_tokens = set(tokens(widget.get("room", "")))
        compatible = COMPATIBLE.get(widget.get("type"), set())
        candidates = []
        for entity in entities:
            eid = entity.get("entity_id", "")
            if eid.split(".", 1)[0] not in compatible:
                continue
            name_tokens = set(tokens(entity.get("name", "")))
            id_tokens = set(tokens(eid.split(".", 1)[-1].replace("_", " ")))
            matched = widget_tokens & (name_tokens | id_tokens)
            if not widget_tokens or not matched:
                continue
            # Exact word matching prevents L1 from being confused with L10.
            coverage = len(matched) / len(widget_tokens)
            exact = widget_tokens == name_tokens or widget_tokens == id_tokens
            room_match = bool(room_tokens & (name_tokens | id_tokens))
            role = classify_entity(entity)
            score = round(min(1, coverage * 0.72 + (0.23 if exact else 0) + (0.05 if room_match else 0)), 2)
            if role == "feedback_probabile":
                score = round(max(0, score - 0.45), 2)
            elif role == "da_verificare":
                score = round(max(0, score - 0.18), 2)
            if eid in used and eid != current:
                score = 0  # Do not recommend an HA entity already linked elsewhere.
            if score:
                candidates.append({"entity_id": eid, "name": entity.get("name", eid), "score": score, "role_hint": role,
                                   "reason": "Nome coincidente" if exact else "Parole in comune"})
        candidates.sort(key=lambda c: (-c["score"], c["entity_id"]))
        leading = candidates[0] if candidates else None
        runner = candidates[1]["score"] if len(candidates) > 1 else 0
        unambiguous = bool(leading and leading["role_hint"] == "funzione_candidata"
                           and leading["score"] >= 0.7 and leading["score"] - runner >= 0.2
                           and leading["entity_id"] not in proposed)
        if unambiguous and not current:
            proposed.add(leading["entity_id"])
        confidence = "alta" if unambiguous and leading["score"] >= 0.9 else "media" if unambiguous else "da verificare"
        proposals.append({"index": index, "name": widget.get("name", ""), "room": widget.get("room", ""),
                          "type": widget.get("type", ""), "current_entity_id": current,
                          "suggested_entity_id": leading["entity_id"] if unambiguous and not current else "",
                          "confidence": confidence if not current else "già associato",
                          "candidates": candidates[:6],
                          "compatible_entities": [{"entity_id": e["entity_id"], "name": e.get("name", e["entity_id"]),
                                                   "role_hint": classify_entity(e)}
                                                  for e in sorted(entities, key=lambda x: x.get("name", ""))
                                                  if e.get("entity_id", "").split(".", 1)[0] in compatible]})
    roles = {eid: classify_entity(entity) for eid, entity in indexed.items()}
    return {"proposals": proposals, "total": len(widgets), "linked": sum(bool(w.get("entity_id")) for w in widgets),
            "suggested": sum(bool(p["suggested_entity_id"]) for p in proposals),
            "inventory_count": len(indexed), "role_hints": roles,
            "review_count": sum(role != "funzione_candidata" for role in roles.values())}
