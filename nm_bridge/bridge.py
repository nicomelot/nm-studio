"""NM Bridge 0.2: read-only HA inventory and locally persisted UI layout."""

import json
import logging
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
from native_areas import synchronize_saved
from ets_import import MAX_ARCHIVE, preview as ets_preview
from ets_archive import decode_upload, MAX_PASSWORD_BYTES
from knx_devices import read_devices, confirm_devices
from audit_notes import read_notes, save_notes
from widget_layout import read_layout as read_widget_layout, save_layout as save_widget_layout, LAYOUT_LOCK
from backend_checks import inspect_configuration, export_backup
from ha_generator import generate as ha_knx_preview, validate_evidence
from nm_link import read_links, save_links, analyze as analyze_links, simulate as simulate_link
from lovelace_generator import generate as generate_dashboard
from dashboard_publisher import publish as publish_dashboard, preview_update as preview_dashboard_update, update_existing as update_dashboard_existing
from entity_matcher import suggest as suggest_entities
from missing_ha_generator import preview as preview_missing_ha, review as review_missing_ha
from deployment_preflight import preflight as deployment_preflight
from knx_panel_bridge import inspect as inspect_knx_panel
from knx_entity_audit import audit as audit_knx_entities
from knx_yaml_audit import inspect_yaml as inspect_knx_yaml
from knx_entity_plan import build as build_knx_entity_plan
from knx_panel_apply import create_one as create_knx_entity
from knx_install import install_step
from commissioning import command as commissioning_command
from installation_review import preview as installation_preview, apply_one as installation_apply
from migration_bundle import export_bundle as export_migration, restore_bundle as restore_migration
from intelligence import summarize as intelligence_summary, decision_entity, normalize_history, history_path
from module_plan import read as read_module_plan, save as save_module_plan, suggest_entities as suggest_module_entities
from floorplan import read as read_floorplans, save as save_floorplans
from floorplan_lovelace import generate as generate_floorplan_dashboard
from floorplan_publisher import publish as publish_floorplan_dashboard
from lab_virtual import (inspect as inspect_virtual_lab, install as install_virtual_lab, replace as replace_virtual_lab,
                         packages_setup_preview, enable_packages)
from lab_devices import candidates as lab_candidates
from lab_dashboard import (preview as lab_dashboard_preview, publish as lab_dashboard_publish,
                           inspect_existing as lab_dashboard_existing, update as lab_dashboard_update)
from bus_recorder import Recorder
from project_sessions import Sessions
from knx_history import query as query_knx_history

LOG = logging.getLogger("nm_bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HA_URL = os.getenv("NM_HA_API", "http://supervisor/core/api/states")
INGRESS_PROXY = "172.30.32.2"
DOMAINS = {"light", "cover", "switch", "scene", "climate", "sensor", "binary_sensor"}
CONFIG_PATH = Path(os.getenv("NM_CONFIG_PATH", "/data/nm_control_layout.json"))
MAX_BODY = 65536
BUS_RECORDER = Recorder(CONFIG_PATH.parent / "nm_knx_events.sqlite")
PROJECTS = Sessions(CONFIG_PATH.parent / "nm_projects")


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


def get_decision_history():
    """Read a bounded HA Recorder window; shrink it when the response is too large."""
    entity = decision_entity(get_ha_states())
    if not entity:
        return {"available": False, "reason": "Motore simulato non rilevato", "items": []}
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Supervisor token is unavailable")
    now = datetime.now(timezone.utc)
    origin = urlsplit(HA_URL)
    query = urlencode({"filter_entity_id": entity, "end_time": now.isoformat(),
                       "significant_changes_only": "0"})
    for hours in (24, 6, 1):
        start = (now - timedelta(hours=hours)).isoformat()
        url = urlunsplit((origin.scheme, origin.netloc, history_path(origin.path) + start, query, ""))
        req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        with urlopen(req, timeout=8) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            LOG.info("Recorder response exceeded 2MB; shrinking window from %s hours", hours)
            continue
        items = normalize_history(json.loads(raw), now)
        return {"available": True, "source": "Home Assistant Recorder", "hours": hours,
                "items": items, "note": "Lo storico dipende da Recorder e dagli attributi registrati."}
    raise ValueError("HA Recorder response too large")


def get_entities():
    raw = get_ha_states()
    items = []
    for entry in raw:
        entity_id = entry.get("entity_id", "")
        if entity_id.split(".", 1)[0] not in DOMAINS | {'button', 'number'}:
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
        if path in ("/projects", "/projects/resume", "/projects/export"):
            try:
                key = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
                data = PROJECTS.list() if path == "/projects" else PROJECTS.resume(key) if path.endswith("resume") else PROJECTS.read(key)
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (ValueError, OSError, KeyError):
                self.respond(400, "application/json", b'{"error":"Progetto non disponibile"}')
        elif path == "/bus-log":
            try:
                query = parse_qs(urlsplit(self.path).query)
                filters = {key: query.get(key, [None])[0] for key in ("ga", "source", "start", "end", "before")}
                self.respond(200, "application/json; charset=utf-8", json.dumps(BUS_RECORDER.snapshot(**filters)).encode())
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                self.respond(500, "application/json", b'{"error":"Registro non disponibile"}')
        elif path == "/entities":
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
        elif path == "/intelligence/history":
            try:
                result = get_decision_history()
                self.respond(200, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError) as exc:
                if isinstance(exc, HTTPError):
                    reason = f"Home Assistant Recorder: HTTP {exc.code}"
                    code = "http_error"
                elif isinstance(exc, json.JSONDecodeError):
                    reason, code = "Recorder ha restituito JSON non valido", "invalid_json"
                elif isinstance(exc, ValueError) and str(exc) == "HA Recorder response too large":
                    reason, code = "Risposta Recorder oltre il limite di 2 MB (24 ore)", "response_too_large"
                elif isinstance(exc, ValueError) and str(exc) == "Unexpected HA Recorder response":
                    reason, code = "Recorder ha restituito un formato inatteso", "unexpected_format"
                else:
                    reason, code = "Storico Home Assistant non disponibile", "read_failed"
                LOG.warning("Intelligence Recorder read failed (%s: %s)", type(exc).__name__, code)
                self.respond(200, "application/json; charset=utf-8", json.dumps({"available": False,
                    "reason": reason, "code": code, "items": []}).encode())
        elif path == "/layout":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps(read_layout(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                LOG.warning("Layout read failed (%s)", type(exc).__name__)
                self.respond(500, "application/json", b'{"error":"Layout unavailable"}')
        elif path == "/modules/plan":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps(read_module_plan(), ensure_ascii=False).encode())
            except (ValueError, OSError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Module checklist unavailable"}')
        elif path == "/floorplans":
            try:
                self.respond(200, "application/json; charset=utf-8", json.dumps(read_floorplans(), ensure_ascii=False).encode())
            except (ValueError, OSError, TypeError, json.JSONDecodeError):
                self.respond(500, "application/json", b'{"error":"Floorplans unavailable"}')
        elif path == "/floorplans/dashboard-preview":
            try:
                data = generate_floorplan_dashboard(read_floorplans(), get_entities())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (ValueError, OSError, HTTPError, URLError, RuntimeError, TypeError, json.JSONDecodeError):
                self.respond(502, "application/json", b'{"error":"Anteprima planimetria HA non disponibile"}')
        elif path == "/modules/suggestions":
            try:
                data = suggest_module_entities(get_entities())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError):
                self.respond(502, "application/json", b'{"error":"Home Assistant suggestions unavailable"}')
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
        elif path == "/knx/installation-review":
            try:
                data = installation_preview(read_widget_layout())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (ValueError, RuntimeError, OSError, TypeError, KeyError):
                self.respond(502, "application/json", b'{"error":"Confronto KNX non disponibile"}')
        elif path == "/dashboard/missing-ha":
            try:
                data = preview_missing_ha(read_widget_layout(), get_entities())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except (HTTPError, URLError, ValueError, RuntimeError, OSError, TypeError, KeyError, json.JSONDecodeError):
                self.respond(502, "application/json", b'{"error":"Cannot prepare missing HA draft"}')
        elif path == "/knx/panel-capability":
            data = inspect_knx_panel()
            self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
        elif path == "/knx/entity-audit":
            try:
                data = audit_knx_entities(read_widget_layout())
                self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
            except Exception as exc:
                LOG.warning("KNX entity audit unavailable (%s)", type(exc).__name__)
                self.respond(200, "application/json; charset=utf-8", json.dumps({"read_only": True,
                    "available": False, "rows": [], "total": 0,
                    "message": "Indice KNX non accessibile: l'add-on potrebbe non avere i permessi amministratore necessari. Verifica dal pannello KNX di Home Assistant."}).encode())
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
        elif path == "/recovery_ui.js":
            self.respond(200, "text/javascript; charset=utf-8", Path(__file__).with_name("recovery_ui.js").read_bytes())
        elif path == "/real_ui.js":
            self.respond(200, "text/javascript; charset=utf-8", Path(__file__).with_name("real_ui.js").read_bytes())
        elif path == "/lab_ui.js":
            self.respond(200, "text/javascript; charset=utf-8", Path(__file__).with_name("lab_ui.js").read_bytes())
        elif path == "/project_ui.js":
            self.respond(200, "text/javascript; charset=utf-8", Path(__file__).with_name("project_ui.js").read_bytes())
        elif path in ("", "/"):
            self.respond(200, "text/html; charset=utf-8", HTML)
        else:
            self.send_error(404)

    def respond(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if self.client_address[0] != INGRESS_PROXY or path not in ("/knx/history", "/lab/dashboard-existing", "/lab/dashboard-update", "/projects/save", "/bus-log/start", "/bus-log/stop", "/layout", "/modules/plan", "/floorplans", "/floorplans/dashboard-publish", "/ets/preview", "/knx/approved", "/audit", "/knx/widgets", "/knx/ha-preview", "/knx/yaml-audit", "/dashboard/missing-ha/review", "/dashboard/deployment-preflight", "/knx/panel-create-plan", "/knx/panel-create-one", "/knx/install-step", "/knx/installation-apply", "/knx/commission-command", "/native/areas-sync", "/dashboard/publish", "/dashboard/update-preview", "/dashboard/update", "/migration/restore", "/nm-link", "/nm-link/preview", "/nm-link/simulate", "/lab/preview", "/lab/install", "/lab/replace", "/lab/packages-preview", "/lab/packages-enable", "/lab/dashboard-preview", "/lab/dashboard-publish"):
            self.send_error(403)
            return
        # Ingress protects access; these checks also reject cross-site form POSTs.
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        expected_types = ("application/octet-stream", "application/vnd.nm.ets-upload") if path == "/ets/preview" else ("application/json",)
        if content_type not in expected_types or self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            self.send_error(415)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            max_body = MAX_ARCHIVE if path == "/ets/preview" else 4 * 1024 * 1024 if path == "/floorplans" else 1024 * 1024 if path == "/migration/restore" else 256 * 1024 if path in ("/knx/widgets", "/knx/ha-preview", "/knx/yaml-audit") else 256 * 1024 if path == "/projects/save" else MAX_BODY
            if path == "/ets/preview" and content_type == "application/vnd.nm.ets-upload":
                max_body += MAX_PASSWORD_BYTES + 4
            if not 0 < n <= max_body:
                raise ValueError("Invalid length")
            body = self.rfile.read(n)
            if path == "/knx/history":
                data = query_knx_history(json.loads(body))
            elif path == "/projects/save":
                data = PROJECTS.save(json.loads(body))
            elif path == "/bus-log/start":
                data = BUS_RECORDER.start(json.loads(body))
            elif path == "/bus-log/stop":
                data = BUS_RECORDER.stop()
            elif path == "/layout":
                layout = validate_layout(json.loads(body))
                write_layout(layout)
                data = {"saved": True}
            elif path == "/modules/plan":
                data = save_module_plan(json.loads(body))
            elif path == "/floorplans":
                data = save_floorplans(json.loads(body))
            elif path == "/floorplans/dashboard-publish":
                data = publish_floorplan_dashboard(json.loads(body), read_floorplans(), get_entities())
            elif path == "/knx/approved":
                data = confirm_devices(json.loads(body))
            elif path == "/knx/widgets":
                data = save_widget_layout(json.loads(body))
            elif path == "/knx/ha-preview":
                saved = read_widget_layout()
                evidence = validate_evidence(json.loads(body), saved["project"])
                data = ha_knx_preview(saved, evidence)
            elif path == "/knx/yaml-audit":
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError("Richiesta non valida")
                data = inspect_knx_yaml(payload.get("yaml"))
            elif path == "/dashboard/missing-ha/review":
                data = review_missing_ha(read_widget_layout(), json.loads(body))
            elif path == "/dashboard/deployment-preflight":
                data = deployment_preflight(read_widget_layout(), json.loads(body), get_entities())
            elif path == "/knx/panel-create-plan":
                data = build_knx_entity_plan(read_widget_layout(), json.loads(body))
            elif path == "/native/areas-sync":
                data = synchronize_saved(json.loads(body))
            elif path == "/knx/commission-command":
                data = commissioning_command(json.loads(body))
            elif path == "/knx/installation-apply":
                data = installation_apply(json.loads(body))
            elif path == "/knx/install-step":
                data = install_step(json.loads(body))
            elif path == "/knx/panel-create-one":
                with LAYOUT_LOCK:
                    data = create_knx_entity(read_widget_layout(), json.loads(body))
            elif path == "/migration/restore":
                request = json.loads(body)
                if not isinstance(request, dict):
                    raise ValueError("Invalid migration request")
                data = restore_migration(request.get("bundle"), CONFIG_PATH, validate_layout,
                                         confirm=request.get("confirm") is True,
                                         overwrite=request.get("overwrite") is True)
            elif path == "/dashboard/update-preview":
                data = preview_dashboard_update(json.loads(body), read_widget_layout(), get_entities())
            elif path == "/dashboard/update":
                data = update_dashboard_existing(json.loads(body), read_widget_layout(), get_entities())
            elif path == "/dashboard/publish":
                data = publish_dashboard(json.loads(body), read_widget_layout(), get_entities())
            elif path == "/lab/preview":
                data = inspect_virtual_lab(json.loads(body))
            elif path == "/lab/dashboard-preview":
                data = lab_dashboard_preview(json.loads(body), get_ha_states())
            elif path == "/lab/dashboard-existing":
                data = lab_dashboard_existing(json.loads(body), get_ha_states())
            elif path == "/lab/dashboard-update":
                data = lab_dashboard_update(json.loads(body), get_ha_states())
            elif path == "/lab/dashboard-publish":
                data = lab_dashboard_publish(json.loads(body), get_ha_states())
            elif path == "/lab/install":
                data = install_virtual_lab(json.loads(body))
            elif path == "/lab/replace":
                data = replace_virtual_lab(json.loads(body))
            elif path == "/lab/packages-preview":
                data = packages_setup_preview()
            elif path == "/lab/packages-enable":
                data = enable_packages(json.loads(body))
            elif path == "/nm-link":
                data = save_links(json.loads(body))
            elif path == "/nm-link/preview":
                data = analyze_links(json.loads(body))
            elif path == "/nm-link/simulate":
                data = simulate_link(json.loads(body))
            elif path == "/audit":
                data = save_notes(json.loads(body))
            else:
                raw, password = decode_upload(body, content_type, MAX_ARCHIVE)
                try:
                    data = ets_preview(raw, password=password)
                finally:
                    password = raw = body = None
                data["lab_candidates"] = lab_candidates(data)
                data = PROJECTS.prepare(data)
            self.respond(200, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())
        except (ValueError, UnicodeDecodeError, OSError, json.JSONDecodeError, RuntimeError) as exc:
            LOG.warning("Request rejected (%s): %s", type(exc).__name__, str(exc)[:160])
            detail = str(exc) if isinstance(exc, ValueError) else "Invalid request or unsupported project"
            self.respond(400, "application/json; charset=utf-8", json.dumps({"error": detail[:160]}, ensure_ascii=False).encode())


if __name__ == "__main__":
    LOG.info("Starting read-only bridge behind Home Assistant Ingress")
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()

