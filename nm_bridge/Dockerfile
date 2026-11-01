ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-websocket-client
COPY bridge.py /app/bridge.py
COPY index.html /app/index.html
COPY ets_import.py /app/ets_import.py
COPY knx_devices.py /app/knx_devices.py
COPY audit_notes.py /app/audit_notes.py
COPY widget_layout.py /app/widget_layout.py
COPY backend_checks.py /app/backend_checks.py
COPY ha_generator.py /app/ha_generator.py
COPY nm_link.py /app/nm_link.py
COPY dpt_registry.py /app/dpt_registry.py
COPY function_engine.py /app/function_engine.py
COPY ets_rooms.py /app/ets_rooms.py
COPY lovelace_generator.py /app/lovelace_generator.py
COPY dashboard_publisher.py /app/dashboard_publisher.py
COPY entity_matcher.py /app/entity_matcher.py
COPY missing_ha_generator.py /app/missing_ha_generator.py
COPY deployment_preflight.py /app/deployment_preflight.py
COPY knx_panel_bridge.py /app/knx_panel_bridge.py
COPY knx_entity_plan.py /app/knx_entity_plan.py
COPY knx_panel_apply.py /app/knx_panel_apply.py
COPY migration_bundle.py /app/migration_bundle.py
COPY intelligence.py /app/intelligence.py
COPY module_plan.py /app/module_plan.py
COPY floorplan.py /app/floorplan.py
COPY floorplan_lovelace.py /app/floorplan_lovelace.py
COPY floorplan_publisher.py /app/floorplan_publisher.py
WORKDIR /app
CMD ["/command/with-contenv", "python3", "-u", "/app/bridge.py"]
