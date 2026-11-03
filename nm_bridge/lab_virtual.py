"""Confirmed NM Lab installation/replacement and optional packages setup.

Writes only the owned NM Lab package, explicit packages include and backups.
Never restarts HA, sends KNX telegrams or alters other packages.
"""

import hashlib
import json
import os
import re
import tempfile
from functools import wraps
from threading import RLock
from datetime import datetime, timezone
from pathlib import Path

try:
    from .lab_devices import build as build_devices
except ImportError:
    from lab_devices import build as build_devices


MAX_ZONES = 30
GA = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])/[0-7]/(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
TARGET_NAME = "nm_lab_virtual.yaml"
INCLUDE_LINE = "  packages: !include_dir_named packages"
WRITE_LOCK = RLock()


def serialized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with WRITE_LOCK:
            return function(*args, **kwargs)
    return wrapped


def _owned_package(content):
    if content.startswith(b"# NM Control - laboratorio virtuale; nessun dispositivo KNX associato."):
        return True
    try:
        data = json.loads(content)
        if not isinstance(data, dict) or not data or set(data) - {"input_boolean", "input_number", "input_button", "template", "climate"}:
            return False
        for domain in ("input_boolean", "input_number", "input_button"):
            if not isinstance(data.get(domain, {}), dict) or any(not key.startswith("nm_lab_") for key in data.get(domain, {})):
                return False
        for group in data.get("template", []):
            for entities in group.values():
                if any(not entity.get("unique_id", "").startswith("nm_lab_") for entity in entities):
                    return False
        return all(entity.get("unique_id", "").startswith("nm_lab_") for entity in data.get("climate", []))
    except (ValueError, TypeError, AttributeError):
        return False


def _packages_enabled(raw):
    """Accept only a direct packages child of the top-level HA mapping."""
    in_homeassistant = False
    found = False
    mappings = 0
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            in_homeassistant = bool(re.fullmatch(r"homeassistant:\s*(?:#.*)?", line))
            mappings += int(in_homeassistant)
        elif in_homeassistant and re.fullmatch(r"  packages:\s*!include_dir_named\s+packages\s*(?:#.*)?", line):
            found = True
    return found and mappings == 1


def _zones(payload):
    if not isinstance(payload, dict) or payload.get("mode") != "virtual_climate":
        raise ValueError("Modalità di laboratorio non valida")
    zones = payload.get("zones")
    if not isinstance(zones, list) or not 1 <= len(zones) <= MAX_ZONES:
        raise ValueError("Seleziona da 1 a 30 zone climatiche")
    keys = set()
    result = []
    for item in zones:
        if not isinstance(item, dict) or item.get("kind") != "climate":
            raise ValueError("Il laboratorio accetta solo termostati riconosciuti")
        command, sensor = item.get("command"), item.get("temperature")
        if not isinstance(command, str) or not GA.fullmatch(command) or not isinstance(sensor, str) or not GA.fullmatch(sensor):
            raise ValueError("Indirizzi ETS non validi")
        if command == sensor or command in keys:
            raise ValueError("Zona duplicata o temperatura senza indirizzo distinto")
        keys.add(command)
        result.append((command, sensor))
    return sorted(result, key=lambda z: tuple(map(int, z[0].split("/"))))


def build(payload):
    if isinstance(payload, dict) and payload.get("mode") == "virtual_devices":
        return build_devices(payload)
    zones = _zones(payload)
    lines = ["# NM Control - laboratorio virtuale; nessun dispositivo KNX associato.",
             "# Creato solo dopo conferma. Rimozione: eliminare nm_lab_virtual.yaml.", ""]
    sections = {"input_boolean": [], "input_number": [], "template": [], "climate": []}
    for command, sensor in zones:
        prefix = "nm_lab_" + command.replace("/", "_")
        label = "NM LAB zona " + command.rsplit("/", 1)[0].replace("/", "-")
        sections["input_boolean"] += [f"  {prefix}_heater:", f"    name: '{label} riscaldamento virtuale'",
                                       "    icon: mdi:radiator", "    initial: false"]
        sections["input_number"] += [f"  {prefix}_temperature:", f"    name: '{label} temperatura virtuale'",
                                      "    min: 10", "    max: 35", "    step: 0.5", "    initial: 20",
                                      "    unit_of_measurement: '°C'"]
        sections["template"] += ["  - sensor:", f"      - name: '{prefix}_temperatura'",
                                 f"        unique_id: {prefix}_sensor", "        device_class: temperature",
                                 "        unit_of_measurement: '°C'", "        state: >-",
                                 f"          {{{{ states('input_number.{prefix}_temperature') | float(20) }}}}"]
        sections["climate"] += ["  - platform: generic_thermostat", f"    name: '{label}'",
                                f"    unique_id: {prefix}_climate", f"    heater: input_boolean.{prefix}_heater",
                                f"    target_sensor: sensor.{prefix}_temperatura",
                                "    min_temp: 15", "    max_temp: 30", "    target_temp: 21",
                                "    precision: 0.5", "    initial_hvac_mode: 'off'"]
    for section in ("input_boolean", "input_number", "template", "climate"):
        lines.append(section + ":")
        lines.extend(sections[section]);lines.append("")
    content = "\n".join(lines)
    return {"yaml": content, "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "zones": len(zones), "knx_traffic": False, "restart_required": True,
            "message": "Entità virtuali; non rappresentano la temperatura reale degli ambienti"}


def _paths(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Cartella di configurazione HA non disponibile")
    packages = root / "packages"
    if packages.is_symlink() or (packages.exists() and not packages.is_dir()):
        raise ValueError("Cartella packages non sicura")
    target = packages / TARGET_NAME
    if target.is_symlink():
        raise ValueError("File NM Lab non sicuro")
    return root, packages, target


def inspect(payload, root="/homeassistant"):
    plan = build(payload)
    root, packages, target = _paths(root)
    config = root / "configuration.yaml"
    raw = config.read_text(encoding="utf-8") if config.is_file() and not config.is_symlink() else ""
    enabled = _packages_enabled(raw)
    existing = target.is_file()
    current = target.read_bytes() if existing and target.stat().st_size < 2_000_000 else b""
    return {"sha256": plan["sha256"], "zones": plan["zones"],
            "devices": plan.get("devices", plan["zones"]), "counts": plan.get("counts", {"climate": plan["zones"]}),
            "manifest": plan.get("manifest", []), "message": plan["message"], "knx_traffic": False, "ready": enabled,
            "already_installed": existing and current == plan["yaml"].encode(),
            "blocked_by_existing": existing and current != plan["yaml"].encode(),
            "replaceable": existing and _owned_package(current),
            "existing_sha256": hashlib.sha256(current).hexdigest() if current else None,
            "packages_enabled": enabled, "target": "packages/" + TARGET_NAME,
            "write_scope": "Solo package NM Lab; configuration.yaml non viene modificato",
            "restart_required": True}


def _configuration_change(root):
    """Prepare a minimal, auditable edit; refuse complex/ambiguous YAML.

    We do not parse arbitrary Home Assistant YAML tags, so only insert into a
    conventional top-level `homeassistant:` mapping or create that mapping.
    """
    root, _, _ = _paths(root)
    config = root / "configuration.yaml"
    if not config.is_file() or config.is_symlink() or not 0 < config.stat().st_size <= 256_000:
        raise ValueError("configuration.yaml assente, simbolico o troppo grande")
    original = config.read_bytes()
    try:
        source = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("configuration.yaml non è UTF-8") from exc
    newline = "\r\n" if b"\r\n" in original else "\n"
    lines = source.splitlines(keepends=True)
    active = [(i, line.rstrip("\r\n")) for i, line in enumerate(lines)
              if line.strip() and not line.lstrip().startswith("#")]
    # A pre-existing packages key may have a custom include, or come from a
    # merge. Never change or override it without installer inspection.
    if any(re.match(r"^\s*packages\s*:", line) for _, line in active):
        raise ValueError("Esiste già una voce packages: verifica manuale necessaria")
    candidates = [(i, line) for i, line in active if re.match(r"^homeassistant\s*:", line)]
    if len(candidates) > 1 or (candidates and candidates[0][1].strip() != "homeassistant:"):
        raise ValueError("Struttura homeassistant non standard: nessuna modifica eseguita")
    if candidates:
        pos = candidates[0][0] + 1
        # Only insert if the following meaningful item is nested or another
        # top-level key; a multiline scalar would make this unsafe.
        for next_line in lines[pos:]:
            if next_line.strip() and not next_line.lstrip().startswith("#"):
                if next_line.startswith(("|", ">")):
                    raise ValueError("Configurazione non standard")
                if next_line.startswith((" ", "\t")) and (not next_line.startswith("  ") or next_line.startswith("   ")):
                    raise ValueError("Indentazione homeassistant non standard: verifica manuale necessaria")
                break
        if not lines[pos - 1].endswith(("\n", "\r")):
            lines[pos - 1] += newline
        proposed = "".join(lines[:pos]) + INCLUDE_LINE + newline + "".join(lines[pos:])
    else:
        proposed = "homeassistant:" + newline + INCLUDE_LINE + newline + newline + source
    return config, original, proposed.encode("utf-8")


def packages_setup_preview(root="/homeassistant"):
    root, _, _ = _paths(root)
    config = root / "configuration.yaml"
    if config.is_file() and not config.is_symlink():
        raw = config.read_text(encoding="utf-8")
        if _packages_enabled(raw):
            return {"already_enabled": True, "ready": True, "preview": "Nessuna modifica necessaria"}
    _, before, after = _configuration_change(root)
    return {"already_enabled": False, "ready": True,
            "expected_sha256": hashlib.sha256(before).hexdigest(),
            "preview": "Aggiungi a configuration.yaml:\n" + "homeassistant:\n" + INCLUDE_LINE,
            "before_bytes": len(before), "after_bytes": len(after),
            "backup_required": True, "restart_required": True}


@serialized
def enable_packages(payload, root="/homeassistant", backup_root="/data/nm_lab_backups"):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise ValueError("Conferma esplicita obbligatoria")
    config, before, after = _configuration_change(root)
    expected = hashlib.sha256(before).hexdigest()
    if payload.get("expected_sha256") != expected:
        raise ValueError("configuration.yaml modificato dopo l'anteprima: ripeti la verifica")
    backups = Path(backup_root)
    backups.mkdir(parents=True, exist_ok=True)
    if backups.is_symlink() or not backups.is_dir():
        raise ValueError("Percorso backup non sicuro")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"configuration-{stamp}-{expected[:12]}.yaml"
    with backup.open("xb") as file:
        file.write(before);file.flush();os.fsync(file.fileno())
    _, packages, _ = _paths(root)
    packages.mkdir(exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=config.parent, prefix=".nm_lab_config_", delete=False) as file:
            temporary = Path(file.name)
            file.write(after);file.flush();os.fsync(file.fileno())
        os.chmod(temporary, config.stat().st_mode & 0o777)
        # Defend against a config changed between preview and the final write.
        if config.is_symlink() or hashlib.sha256(config.read_bytes()).hexdigest() != expected:
            raise ValueError("configuration.yaml modificato durante il salvataggio")
        os.replace(temporary, config)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"enabled": True, "backup_created": True, "restart_required": True,
            "message": "Verifica YAML e riavvia Home Assistant; nessun riavvio automatico"}


@serialized
def install(payload, root="/homeassistant"):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise ValueError("Conferma esplicita obbligatoria")
    plan = build(payload)
    if payload.get("expected_sha256") != plan["sha256"]:
        raise ValueError("Anteprima non aggiornata: ripeti la verifica")
    status = inspect(payload, root)
    if not status["ready"]:
        raise ValueError("Abilita prima i packages di Home Assistant in configuration.yaml")
    if status["blocked_by_existing"]:
        raise ValueError("Package NM Lab esistente differente: nessuna sovrascrittura")
    if status["already_installed"]:
        return {"installed": True, "unchanged": True, **status}
    _, packages, target = _paths(root)
    packages.mkdir(exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=packages, prefix=".nm_lab_", delete=False) as file:
            temp = Path(file.name)
            file.write(plan["yaml"])
            file.flush();os.fsync(file.fileno())
        # Exclusive creation: never overwrite a file even if it appeared since inspect.
        if os.name == "nt":
            # Windows rename is exclusive (unlike POSIX rename), and does not
            # require the hard-link privilege unavailable in restricted hosts.
            os.rename(temp, target)
        else:
            os.link(temp, target)
    except FileExistsError as exc:
        raise ValueError("Il file NM Lab è già presente; nessuna sovrascrittura") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return {"installed": True, "unchanged": False, **status}


@serialized
def replace(payload, root="/homeassistant", backup_root="/data/nm_lab_backups"):
    """Replace only an identified NM Lab package after preview and byte-exact backup."""
    if not isinstance(payload, dict) or payload.get("confirm") is not True or payload.get("replace_confirmed") is not True:
        raise ValueError("Conferma esplicita della sostituzione obbligatoria")
    plan = build(payload)
    status = inspect(payload, root)
    if payload.get("expected_sha256") != plan["sha256"] or payload.get("expected_existing_sha256") != status["existing_sha256"]:
        raise ValueError("Package modificato dopo l'anteprima: ripeti la verifica")
    if not status["ready"] or not status["replaceable"]:
        raise ValueError("Sostituzione consentita solo per un package NM Lab riconosciuto con packages abilitati")
    _, _, target = _paths(root)
    before = target.read_bytes()
    if hashlib.sha256(before).hexdigest() != status["existing_sha256"]:
        raise ValueError("Package modificato durante il salvataggio")
    backups = Path(backup_root)
    if backups.is_symlink():
        raise ValueError("Percorso backup non sicuro")
    backups.mkdir(parents=True, exist_ok=True)
    # Unique backup per operation, also for repeated replacements in one second.
    with tempfile.NamedTemporaryFile("wb", dir=backups, prefix="nm_lab_virtual_", suffix=".yaml", delete=False) as file:
        file.write(before); file.flush(); os.fsync(file.fileno())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".nm_lab_", delete=False) as file:
            temporary = Path(file.name)
            file.write(plan["yaml"].encode()); file.flush(); os.fsync(file.fileno())
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != status["existing_sha256"]:
            raise ValueError("Package modificato durante il salvataggio")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"installed": True, "replaced": True, "backup_created": True, "restart_required": True, "knx_traffic": False}

