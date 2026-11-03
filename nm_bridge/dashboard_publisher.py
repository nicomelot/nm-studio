"""Explicit, create-only Home Assistant Lovelace publisher.

The only writes are to a *new* storage-mode Lovelace dashboard. No KNX APIs,
HA service calls, entity registry writes, or edits to existing dashboards.
"""

import json
import os
import re

try:
    from .lovelace_generator import generate
except ImportError:
    from lovelace_generator import generate


URL_PATH = re.compile(r"^nm-studio-[a-z0-9-]{3,52}$")
# Up to 200 zones, each with a floor, controls and history view.
MAX_VIEWS = 640


class PublishError(ValueError):
    pass


class HAWebSocket:
    def __init__(self, connection=None):
        self.connection = connection
        self.sequence = 0

    def __enter__(self):
        if self.connection is None:
            from websocket import create_connection
            token = os.environ.get("SUPERVISOR_TOKEN")
            if not token:
                raise PublishError("Token Supervisor non disponibile")
            self.connection = create_connection(
                "ws://supervisor/core/websocket", timeout=12,
                header={"Authorization": "Bearer " + token},
                http_proxy_host=None,
            )
        greeting = self._receive()
        if greeting.get("type") == "auth_required":
            self.connection.send(json.dumps({"type": "auth", "access_token": os.environ.get("SUPERVISOR_TOKEN", "")}))
            greeting = self._receive()
        if greeting.get("type") != "auth_ok":
            raise PublishError("Autenticazione WebSocket HA non riuscita")
        return self

    def __exit__(self, *_):
        self.connection.close()

    def _receive(self):
        result = json.loads(self.connection.recv())
        if not isinstance(result, dict):
            raise PublishError("Risposta WebSocket HA non valida")
        return result

    def call(self, type_, **args):
        self.sequence += 1
        command = {"id": self.sequence, "type": type_, **args}
        self.connection.send(json.dumps(command, ensure_ascii=False))
        for _ in range(20):
            response = self._receive()
            if response.get("id") != self.sequence:
                continue
            if response.get("type") != "result" or not response.get("success"):
                detail = response.get("error", {})
                message = detail.get("message", "Operazione rifiutata") if isinstance(detail, dict) else "Operazione rifiutata"
                raise PublishError("Home Assistant: " + str(message)[:180])
            return response.get("result")
        raise PublishError("Nessuna conferma da Home Assistant")


def _listed_paths(raw):
    if isinstance(raw, dict):
        raw = raw.get("dashboards", raw.get("items", []))
    if not isinstance(raw, list):
        raise PublishError("Elenco dashboard HA non riconosciuto: pubblicazione annullata")
    return {entry.get("url_path") for entry in raw if isinstance(entry, dict)}


def publish(payload, layout, entities, client_factory=HAWebSocket):
    return publish_generated(payload, generate(layout, entities), client_factory)


def publish_generated(payload, generated, client_factory=HAWebSocket):
    """Publish a server-generated preview, never a client-supplied configuration."""
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise PublishError("Conferma esplicita obbligatoria")
    url_path = payload.get("url_path")
    title = payload.get("title")
    if not isinstance(url_path, str) or not URL_PATH.fullmatch(url_path):
        raise PublishError("Percorso non valido: usa nm-studio- seguito da lettere, numeri o trattini")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 60:
        raise PublishError("Titolo dashboard non valido")
    if payload.get("expected_fingerprint") != generated["fingerprint"]:
        raise PublishError("Anteprima non aggiornata: rigenera prima di pubblicare")
    if generated["summary"]["tiles"] == 0:
        raise PublishError("Nessuna entità HA compatibile: associa almeno un dispositivo reale prima di pubblicare")
    if not 1 <= len(generated["dashboard"]["views"]) <= MAX_VIEWS:
        raise PublishError("Numero viste inatteso")
    with client_factory() as client:
        existing = _listed_paths(client.call("lovelace/dashboards/list"))
        if url_path in existing:
            raise PublishError("Dashboard già esistente: non viene sovrascritta")
        client.call("lovelace/dashboards/create", url_path=url_path, title=title.strip(),
                    icon="mdi:floor-plan", show_in_sidebar=True, require_admin=False)
        # If save fails the empty dashboard may remain. Never silently delete
        # or retry by overwriting: report the exact path to the installer.
        try:
            client.call("lovelace/config/save", url_path=url_path, config=generated["dashboard"])
        except Exception as exc:
            raise PublishError("Dashboard creata ma configurazione non salvata (" + url_path + "): " + str(exc)[:140]) from exc
        # Confirm a readable config; avoid claiming a successful publish on
        # an unexpected response or mismatched view structure.
        stored = client.call("lovelace/config", url_path=url_path)
        if not isinstance(stored, dict) or stored.get("views") != generated["dashboard"]["views"]:
            raise PublishError("Dashboard creata, ma verifica contenuto non riuscita: " + url_path)
    return {"created": True, "url_path": url_path, "title": title.strip(),
            "summary": generated["summary"], "warnings": generated["warnings"]}

