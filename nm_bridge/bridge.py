"""NM Bridge 0.2: read-only HA inventory and locally persisted UI layout."""

import json
import logging
import os
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, parse_qs
from ets_import import MAX_ARCHIVE, preview as ets_preview
from knx_devices import read_devices, confirm_devices
from audit_notes import read_notes, save_notes
from widget_layout import read_layout as read_widget_layout, save_layout as save_widget_layout
from backend_checks import inspect_configuration, export_backup
from ha_generator import generate as ha_knx_preview, validate_evidence
from nm_link import read_links, save_links, analyze as analyze_links, simulate as simulate_link
from lovelace_generator import generate as generate_dashboard
from dashboard_publisher import publish as publish_dashboard
from entity_matcher import suggest as suggest_entities
from missing_ha_generator import preview as preview_missing_ha, review as review_missing_ha
from deployment_preflight import preflight as deployment_preflight
from knx_panel_bridge import inspect as inspect_knx_panel
from knx_entity_plan import build as build_knx_entity_plan
from migration_bundle import export_bundle as export_migration, restore_bundle as restore_migration
from intelligence import summarize as intelligence_summary

LOG = logging.getLogger("nm_bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HA_URL = os.getenv("NM_HA_API", "http://supervisor/core/api/states")
INGRESS_PROXY = "172.30.32.2"
DOMAINS = {"light", "cover", "switch", "scene", "climate", "sensor", "binary_sensor"}
CONFIG_PATH = Path(os.getenv("NM_CONFIG_PATH", "/data/nm_control_layout.json"))
MAX_BODY = 65536


def get_ha_states():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Supervisor token is unavailable")
    req = Request(HA_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlopen(req, timeout=8) as response:
        raw = json.load(response)
    if not isinstance(raw, list):
        raise ValueError("Unexpected Home Assistant response")
    return raw


def get_entities():
    raw = get_ha_states()
    items = []
    for entry in raw:
        entity_id = entry.get("entity_id", "")
        if entity_id.split(".", 1)[0] not in DOMAINS:
            continue
        attrs = entry.get("attributes") or {}
        items.append({
            "entity_id": entity_id,
            "name": str(attrs.get("friendly_name") or entity_id),
            "state": str(entry.get("state", "unknown")),
            "unit": attrs.get("unit_of_measurement") if isinstance(attrs.get("unit_of_measurement"), str) else None,
            "last_changed": entry.get("last_changed"),
            "brightness": attrs.get("brightness") if isinstance(attrs.get("brightness"), (int, float)) else None,
            "current_position": attrs.get("current_position") if isinstance(attrs.get("current_position"), (int, float)) else None,
            "current_temperature": attrs.get("current_temperature") if isinstance(attrs.get("current_temperature"), (int, float)) else None,
            "temperature": attrs.get("temperature") if isinstance(attrs.get("temperature"), (int, float)) else None,
            "hvac_action": attrs.get("hvac_action") if isinstance(attrs.get("hvac_action"), str) else None,
        })
    return sorted(items, key=lambda item: item["entity_id"])


HTML = Path(__file__).with_name("index.html").read_bytes()


def validate_layout(payload):
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Invalid layout version")
    rooms = payload.get("rooms")
    if not isinstance(rooms, list) or len(rooms) > 50:
        raise ValueError("Invalid rooms")
    ids = set()
    total = 0
    clean = []
    for room in rooms:
        if not isinstance(room, dict):
            raise ValueError("Invalid room")
        rid, name = room.get("id"), room.get("name")
        if not isinstance(rid, str) or not (1 <= len(rid) <= 50) or not rid.isascii() or not all(c.isalnum() or c in "_-" for c in rid) or rid in ids:
            raise ValueError("Invalid room id")
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 80):
            raise ValueError("Invalid room name")
        ids.add(rid)
        widgets = room.get("widgets")
        if not isinstance(widgets, list) or len(widgets) > 100:
            raise ValueError("Invalid widgets")
        total += len(widgets)
        if total > 500:
            raise ValueError("Too many widgets")
        normalized = []
        for widget in widgets:
            if not isinstance(widget, dict):
                raise ValueError("Invalid widget")
            entity = widget.get("entity_id")
            label = widget.get("label")
            if not isinstance(entity, str) or len(entity) > 255 or "." not in entity or entity.split(".", 1)[0] not in DOMAINS:
                raise ValueError("Invalid entity")
            if not isinstance(label, str) or len(label) > 80:
                raise ValueError("Invalid label")
            normalized.append({"entity_id": entity, "label": label})
        clean.append({"id": rid, "name": name.strip(), "widgets": normalized})
    return {"version": 1, "rooms": clean}


def read_layout():
    if not CONFIG_PATH.exists():
        return {"version": 1, "rooms": []}
    return validate_layout(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))


def write_layout(layout):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_PATH.parent, delete=False) as f:
            tmp_path = Path(f.name)
            json.dump(layout, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Ingress is the only intended entrypoint. No host port is exposed.
        if self.client_address[0] != INGRESS_PROXY:
            self.send_error(403)
            return
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/entities":
            try:
                data = json.dumps({"read_only": True, "entities": get_entities()}, ensure_ascii=False).encode()
                self.respond(200, "application/json; charset=utf-8", data)
            except (HTTPError, URLError, ValueError, RuntimeError, OSError) as exc:
                LOG.warning("State query failed (%s)", type(exc).__name__)
                self.respond(502, "application/json", b'{"error":"Home Assistant state query unavailable"}')
        elif path == "/intelligence/summary":
            try:
                data = intelligence_summary(get_ha_states())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError) as exc:
                LOG.warning("Intelligence read failed (%s)", type(exc).__name__)
                self.respond(502, "application/json", b'{"error":"Home Assistant Intelligence state unavailable"}')
        elif path == "/layout":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps(read_layout(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                LOG.warning("Layout read failed (%s)", type(exc).__name__)
                self.respond(500, "application/json", b'{"error":"Layout unavailable"}')
        elif path == "/knx/approved":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps({"devices": read_devices()}, ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Approved devices unavailable"}')
        elif path == "/knx/widgets":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps(read_widget_layout(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"KNX widget layout unavailable"}')
        elif path == "/dashboard/preview":
            try:
                try:
                    inventory = get_entities()
                except (HTTPError, URLError, ValueError, RuntimeError, OSError):
                    LOG.warning("Dashboard preview: HA inventory unavailable; marking links as unresolved")
                    inventory = []
                data = generate_dashboard(read_widget_layout(), inventory)
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Dashboard preview unavailable"}')
        elif path == "/dashboard/matches":
            try:
                data = suggest_entities(read_widget_layout(), get_entities())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError, KeyError, json.JSONDecodeError):
                self.respond(502, "application/json", b'{"error":"HA inventory or associations unavailable"}')
        elif path == "/dashboard/missing-ha":
            try:
                data = preview_missing_ha(read_widget_layout(), get_entities())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError, KeyError, json.JSONDecodeError):
                self.respond(502, "application/json", b'{"error":"Cannot prepare missing HA draft"}')
        elif path == "/knx/panel-capability":
            data = inspect_knx_panel()
            self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
        elif path == "/migration/export":
            try:
                data = export_migration(CONFIG_PATH, validate_layout)
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Migration export unavailable"}')
        elif path == "/knx/preflight":
            try:
                self.respond(200, "application/json; charset=utf-8",
                             json.dumps(inspect_configuration(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError):
                self.respond(500, "application/json", b'{"error":"Configuration diagnostics unavailable"}')
        elif path == "/knx/ha-preview":
            try:
                self.respond(200, "application/json; charset=utf-8",
                             json.dumps(ha_knx_preview(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError):
                self.respond(500, "application/json", b'{"error":"HA KNX preview unavailable"}')
        elif path == "/nm-link":
            try:
                self.respond(200, "application/json; charset=utf-8",
                             json.dumps(read_links(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"NM Link drafts unavailable"}')
        elif path == "/backup":
            try:
                data = json.dumps(export_backup(CONFIG_PATH), ensure_ascii=False).encode()
                self.respond(200, "application/json; charset=utf-8", data)
            except (ValueError, OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Backup unavailable"}')
        elif path == "/audit":
            try:
                project = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
                self.respond(200, "application/json; charset=utf-8", json.dumps({"entries": read_notes(project)}, ensure_ascii=False).encode())
            except ValueError as exc:
                self.respond(400, "application/json", json.dumps({"error": str(exc)[:120]}).encode())
            except (OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Review unavailable"}')
        elif path in ("", "/"):
            self.respond(200, "text/html; charset=utf-8", HTML)
        else:
            self.send_error(404)

    def respond(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if self.client_address[0] != INGRESS_PROXY or path not in ("/layout", "/ets/preview", "/knx/approved", "/audit", "/knx/widgets", "/knx/ha-preview", "/dashboard/missing-ha/review", "/dashboard/deployment-preflight", "/knx/panel-create-plan", "/dashboard/publish", "/migration/restore", "/nm-link", "/nm-link/preview", "/nm-link/simulate"):
            self.send_error(403)
            return
        # Ingress protects access; these checks also reject cross-site form POSTs.
        expected_type = "application/octet-stream" if path == "/ets/preview" else "application/json"
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != expected_type or self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            self.send_error(415)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            max_body = MAX_ARCHIVE if path == "/ets/preview" else 1024 * 1024 if path == "/migration/restore" else 256 * 1024 if path in ("/knx/widgets", "/knx/ha-preview") else MAX_BODY
            if not 0 < n <= max_body:
                raise ValueError("Invalid length")
            body = self.rfile.read(n)
            if path == "/layout":
                layout = validate_layout(json.loads(body))
                write_layout(layout)
                data = {"saved": True}
            elif path == "/knx/approved":
                data = confirm_devices(json.loads(body))
            elif path == "/knx/widgets":
                data = save_widget_layout(json.loads(body))
            elif path == "/knx/ha-preview":
                saved = read_widget_layout()
                evidence = validate_evidence(json.loads(body), saved["project"])
                data = ha_knx_preview(saved, evidence)
            elif path == "/dashboard/missing-ha/review":
                data = review_missing_ha(read_widget_layout(), json.loads(body))
            elif path == "/dashboard/deployment-preflight":
                data = deployment_preflight(read_widget_layout(), json.loads(body), get_entities())
            elif path == "/knx/panel-create-plan":
                data = build_knx_entity_plan(read_widget_layout(), json.loads(body))
            elif path == "/migration/restore":
                request = json.loads(body)
                if not isinstance(request, dict):
                    raise ValueError("Invalid migration request")
                data = restore_migration(request.get("bundle"), CONFIG_PATH, validate_layout,
                                         confirm=request.get("confirm") is True,
                                         overwrite=request.get("overwrite") is True)
            elif path == "/dashboard/publish":
                data = publish_dashboard(json.loads(body), read_widget_layout(), get_entities())
            elif path == "/nm-link":
                data = save_links(json.loads(body))
            elif path == "/nm-link/preview":
                data = analyze_links(json.loads(body))
            elif path == "/nm-link/simulate":
                data = simulate_link(json.loads(body))
            elif path == "/audit":
                data = save_notes(json.loads(body))
            else:
                data = ets_preview(body)
            self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
        except (ValueError, UnicodeDecodeError, OSError, json.JSONDecodeError, RuntimeError) as exc:
            LOG.warning("Request rejected (%s): %s", type(exc).__name__, str(exc)[:160])
            detail = str(exc) if isinstance(exc, ValueError) else "Invalid request or unsupported project"
            self.respond(400, "application/json; charset=utf-8", json.dumps({"error": detail[:160]}, ensure_ascii=False).encode())


if __name__ == "__main__":
    LOG.info("Starting read-only bridge behind Home Assistant Ingress")
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
