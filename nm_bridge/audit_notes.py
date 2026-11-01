"""Installer review notes scoped to a stable ETS project ID. Never contacts KNX."""

import json
import os
import re
import tempfile
from pathlib import Path


NOTES_PATH = Path(os.getenv("NM_ETS_NOTES_PATH", "/data/nm_ets_review.json"))
PROJECT = re.compile(r"^[0-9a-f]{64}$")
ADDRESS = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
STATES = {"todo", "expected", "fix", "verified"}


def read_all():
    if not NOTES_PATH.exists():
        return {}
    data = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or len(data) > 100:
        raise ValueError("Invalid review file")
    return data


def read_notes(project):
    if not PROJECT.fullmatch(project):
        raise ValueError("Invalid project key")
    return read_all().get(project, {})


def save_notes(payload):
    if not isinstance(payload, dict) or not PROJECT.fullmatch(str(payload.get("project", ""))):
        raise ValueError("Invalid project key")
    entries = payload.get("entries")
    if not isinstance(entries, dict) or len(entries) > 6000:
        raise ValueError("Invalid review entries")
    validated = {}
    for ga, record in entries.items():
        if not isinstance(ga, str) or not ADDRESS.fullmatch(ga) or not isinstance(record, dict):
            raise ValueError("Invalid review address")
        state, note = record.get("status"), record.get("note", "")
        if state not in STATES or not isinstance(note, str) or len(note) > 500:
            raise ValueError("Invalid review state or note")
        validated[ga] = {"status": state, "note": note.strip()}
    data = read_all()
    data[payload["project"]] = validated
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=NOTES_PATH.parent, delete=False) as handle:
            temp = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, NOTES_PATH)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"saved": len(validated)}
