"""Generate a disposable, bus-free config for HA's own configuration validator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nm_bridge.lab_devices import build

root = Path(sys.argv[1])
(root / "packages").mkdir(parents=True, exist_ok=True)
(root / "configuration.yaml").write_text("homeassistant:\n  packages: !include_dir_named packages\n", encoding="utf-8")
request = {"mode": "virtual_devices", "project": "a" * 64, "devices": [
    {"kind": kind, "name": kind, "command": f"1/0/{i}", "room": "Test"}
    for i, kind in enumerate(("light", "dimmer", "cover", "scene", "sensor", "binary_sensor", "climate"))]}
(root / "packages" / "nm_lab_virtual.yaml").write_text(build(request)["yaml"], encoding="utf-8")
