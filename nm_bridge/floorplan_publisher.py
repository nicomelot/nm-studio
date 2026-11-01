"""Explicit create-only publisher for native HA Picture Elements dashboards."""

try:
    from .dashboard_publisher import HAWebSocket, PublishError, URL_PATH, _listed_paths
    from .floorplan_lovelace import generate
except ImportError:
    from dashboard_publisher import HAWebSocket, PublishError, URL_PATH, _listed_paths
    from floorplan_lovelace import generate


def publish(payload, archive, entities, client_factory=HAWebSocket):
    if not isinstance(payload, dict) or payload.get("confirm") is not True:
        raise PublishError("Conferma esplicita richiesta")
    title, url_path = payload.get("title"), payload.get("url_path")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 60:
        raise PublishError("Titolo non valido")
    if not isinstance(url_path, str) or not URL_PATH.fullmatch(url_path):
        raise PublishError("Percorso dashboard non valido")
    generated = generate(archive, entities)
    if generated["fingerprint"] != payload.get("expected_fingerprint"):
        raise PublishError("Anteprima non aggiornata: rigenera la planimetria")
    if not generated["summary"]["interactive_points"]:
        raise PublishError("Nessun punto con entità HA esistente: impossibile pubblicare")
    if len(generated["dashboard"]["views"]) > 15:
        raise PublishError("Numero planimetrie superiore al limite")
    with client_factory() as client:
        if url_path in _listed_paths(client.call("lovelace/dashboards/list")):
            raise PublishError("Dashboard già esistente: non viene sovrascritta")
        client.call("lovelace/dashboards/create", url_path=url_path, title=title.strip(),
                    icon="mdi:floor-plan", show_in_sidebar=True, require_admin=False)
        try:
            client.call("lovelace/config/save", url_path=url_path, config=generated["dashboard"])
        except Exception as exc:
            raise PublishError("Dashboard creata, ma salvataggio non riuscito (" + url_path + "): " + str(exc)[:120]) from exc
        stored = client.call("lovelace/config", url_path=url_path)
        if not isinstance(stored, dict) or stored.get("views") != generated["dashboard"]["views"]:
            raise PublishError("Dashboard creata, ma verifica non riuscita: " + url_path)
    return {"created": True, "url_path": url_path, "summary": generated["summary"], "warnings": generated["warnings"]}
