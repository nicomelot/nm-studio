"""Generate a disposable, bus-free config for HA's own configuration validator."""
import sys
from shutil import copyfile
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

# Validate the same blueprint installers import, with a disposable schedule.
blueprint_path = Path("automation/nm_control/cronotermostato.yaml")
blueprint_dir = root / "blueprints"
(blueprint_dir / blueprint_path.parent).mkdir(parents=True, exist_ok=True)
copyfile(Path(__file__).resolve().parents[1] / "blueprints" / blueprint_path, blueprint_dir / blueprint_path)
(root / "packages" / "nm_crono_check.yaml").write_text('''schedule:
  nm_crono:
    name: Crono test
    monday:
      - from: "08:00:00"
        to: "12:00:00"
        data:
          temperature: 22
      - from: "12:00:00"
        to: "18:00:00"
        data:
          temperature: 23
input_boolean:
  nm_crono_manual:
    name: Manuale test
automation:
  - alias: Crono test
    use_blueprint:
      path: nm_control/cronotermostato.yaml
      input:
        thermostat: climate.test
        weekly_schedule: schedule.nm_crono
        manual_override: input_boolean.nm_crono_manual
        operating_mode: heat
        comfort_temperature: 21
''', encoding="utf-8")
