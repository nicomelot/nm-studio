"""Run inside the official HA image; validates drafts without connecting to a bus."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeassistant.components.knx.storage.entity_store_validation import (
    validate_entity_data, EntityStoreValidationException,
)
from nm_bridge.knx_entity_plan import build
from nm_bridge.missing_ha_generator import fingerprint

for kind, fields in (
    ("light", {"command": "1/1/0", "feedback": "1/1/1"}),
    ("light", {"command": "1/1/0"}),
    ("dimmer", {"command": "1/1/0", "feedback": "1/1/1", "brightness": "1/1/2", "brightness_feedback": "1/1/3"}),
    ("cover", {"command": "1/2/0", "stop": "1/2/1"}),
    ("cover", {"command": "1/2/0", "stop": "1/2/1", "position_command": "1/2/2", "position_feedback": "1/2/3"}),
):
    layout = {"version": 1, "project": "a" * 64, "rooms": [], "structure": [],
              "widgets": [{"name": "Synthetic", "room": "Test", "type": kind, "fields": fields}]}
    request = {"source_fingerprint": fingerprint(layout), "devices": [
        {"index": 0, "approved": True, "name": "Synthetic", "fields": fields}]}
    call = build(layout, request)["calls"][0]
    validate_entity_data(call)
    print(f"Official HA KNX schema accepted: {kind} {sorted(fields)}")

try:
    validate_entity_data({"platform": "light", "data": {"name": "Synthetic", "address": "1/1/0"}})
except EntityStoreValidationException:
    print("Confirmed regression: old flat YAML payload is rejected")
else:
    raise AssertionError("Expected old payload to fail KNX panel validation")

# Existing stored light -> dimmer additive update, without entity recreation.
from nm_bridge.installation_review import compare
class Stored:
    def call(self, method, **kwargs):
        if method == 'knx/get_entities_by_group': return {}
        return {'platform': 'light', 'data': {'entity': {'name': 'Existing'}, 'knx': {'ga_switch': {'write': '1/1/0'}}}}
layout = {'version': 1, 'project': 'a'*64, 'widgets': [{'name': 'Imported', 'type': 'dimmer', 'entity_id': 'light.existing', 'fields': {'command': '1/1/0', 'brightness': '1/1/2', 'brightness_feedback': '1/1/3'}}]}
row = compare(layout, 0, Stored())
assert row['status'] == 'update', row
validate_entity_data(row['call'])
print('Official HA schema accepted: additive update preserving entity_id')
