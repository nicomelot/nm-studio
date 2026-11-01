"""Extensible logical KNX DPT catalogue for inert NM Link simulations.

This does NOT encode/decode KNX APDUs. Ranges and categories are validation
guides, not certification of the DPT recorded in ETS.
"""

import math
import re


DPTS = {
    "1.001": ("Commutazione", "boolean", None, None),
    "1.002": ("Booleano", "boolean", None, None),
    "1.005": ("Allarme", "boolean", None, None),
    "1.008": ("Movimento Su/Giù", "boolean", None, None),
    "3.007": ("Dimmerazione relativa", "relative", None, None),
    "5.001": ("Percentuale", "float", 0, 100),
    "5.010": ("Contatore 8 bit", "integer", 0, 255),
    "6.001": ("Intero 8 bit con segno", "integer", -128, 127),
    "7.001": ("Contatore 16 bit", "integer", 0, 65535),
    "8.001": ("Intero 16 bit con segno", "integer", -32768, 32767),
    "9.001": ("Temperatura", "float", -273, 670760),
    "9.004": ("Illuminamento", "float", 0, 670760),
    "9.007": ("Umidità relativa", "float", 0, 100),
    "12.001": ("Contatore 32 bit", "integer", 0, 4294967295),
    "13.001": ("Intero 32 bit con segno", "integer", -2147483648, 2147483647),
    "14.056": ("Potenza", "float", -3.4e38, 3.4e38),
    "16.000": ("Testo ASCII", "text", None, None),
    "17.001": ("Numero scena", "integer", 0, 63),
    "20.102": ("Modalità HVAC", "integer", 0, 255),
    "232.600": ("Colore RGB", "rgb", None, None),
    "251.600": ("Colore RGBW", "rgbw", None, None),
}

LEGACY_DPT = {"boolean": "1.001", "percent": "5.001", "temperature": "9.001"}


def definition(dpt):
    if not isinstance(dpt, str) or dpt not in DPTS:
        raise ValueError("Unsupported KNX DPT in simulator")
    label, kind, minimum, maximum = DPTS[dpt]
    return {"dpt": dpt, "label": label, "kind": kind, "minimum": minimum, "maximum": maximum}


def parse_sample(dpt, raw):
    """Validate an example *logical* value only, without bus conversion."""
    spec = definition(dpt)
    kind = spec["kind"]
    if kind == "boolean":
        if type(raw) is bool:
            return raw
        if isinstance(raw, str) and raw.strip().lower() in ("on", "off", "true", "false", "1", "0"):
            return raw.strip().lower() in ("on", "true", "1")
        raise ValueError("Boolean sample must be ON or OFF")
    if kind == "relative":
        if not isinstance(raw, str):
            raise ValueError("Relative dimming sample must be up:1..7, down:1..7 or stop")
        sample = raw.strip().lower()
        if sample == "stop":
            return {"direction": "stop", "step_code": 0}
        match = re.fullmatch(r"(up|down):([1-7])", sample)
        if not match:
            raise ValueError("Relative dimming sample must be up:1..7, down:1..7 or stop")
        return {"direction": match.group(1), "step_code": int(match.group(2))}
    if kind in ("integer", "float"):
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise ValueError("Numeric sample required")
        try:
            value = float(raw)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Invalid numeric sample") from exc
        if not math.isfinite(value):
            raise ValueError("Sample must be finite")
        if not spec["minimum"] <= value <= spec["maximum"]:
            raise ValueError("Sample outside expected range")
        if kind == "integer":
            if not value.is_integer():
                raise ValueError("Integer sample required")
            return int(value)
        return round(value, 3)
    if kind == "text":
        if not isinstance(raw, str) or not 1 <= len(raw) <= 14 or not raw.isascii() or any(ord(c) < 32 for c in raw):
            raise ValueError("ASCII text sample must contain 1 to 14 printable characters")
        return raw
    if kind in ("rgb", "rgbw"):
        channels = 3 if kind == "rgb" else 4
        if not isinstance(raw, str) or not re.fullmatch(r"#[0-9a-fA-F]{%d}" % (channels * 2), raw):
            raise ValueError("Color sample must be #RRGGBB or #RRGGBBWW")
        return raw.upper()
    raise ValueError("Unsupported DPT simulation category")
