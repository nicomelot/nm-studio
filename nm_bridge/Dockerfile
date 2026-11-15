ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-websocket-client py3-pip poppler-utils \
    && python3 -m venv --system-site-packages /opt/nm-venv
COPY requirements.txt /app/requirements.txt
RUN /opt/nm-venv/bin/pip install --no-cache-dir -r /app/requirements.txt
ENV PATH="/opt/nm-venv/bin:$PATH"
COPY bridge.py /app/bridge.py
COPY index.html /app/index.html
COPY control.html /app/control.html
COPY control.js /app/control.js
COPY control.css /app/control.css
COPY control-dark.css /app/control-dark.css
COPY control_engine.py /app/control_engine.py
COPY lab_ui.js /app/lab_ui.js
COPY ets_import.py /app/ets_import.py
COPY ets_named_functions.py /app/ets_named_functions.py
COPY ets_object_functions.py /app/ets_object_functions.py
COPY ets_archive.py /app/ets_archive.py
COPY recognition.py /app/recognition.py
COPY knx_devices.py /app/knx_devices.py
COPY audit_notes.py /app/audit_notes.py
COPY widget_layout.py /app/widget_layout.py
COPY backend_checks.py /app/backend_checks.py
COPY ha_generator.py /app/ha_generator.py
COPY nm_link.py /app/nm_link.py
COPY dpt_registry.py /app/dpt_registry.py
COPY function_engine.py /app/function_engine.py
COPY ets_rooms.py /app/ets_rooms.py
COPY real_dashboard.py /app/real_dashboard.py
COPY lovelace_generator.py /app/lovelace_generator.py
COPY dashboard_publisher.py /app/dashboard_publisher.py
COPY entity_matcher.py /app/entity_matcher.py
COPY missing_ha_generator.py /app/missing_ha_generator.py
COPY deployment_preflight.py /app/deployment_preflight.py
COPY knx_panel_bridge.py /app/knx_panel_bridge.py
COPY knx_entity_audit.py /app/knx_entity_audit.py
COPY knx_yaml_audit.py /app/knx_yaml_audit.py
COPY knx_entity_plan.py /app/knx_entity_plan.py
COPY knx_panel_apply.py /app/knx_panel_apply.py
COPY knx_install.py /app/knx_install.py
COPY native_areas.py /app/native_areas.py
COPY migration_bundle.py /app/migration_bundle.py
COPY intelligence.py /app/intelligence.py
COPY module_plan.py /app/module_plan.py
COPY floorplan.py /app/floorplan.py
COPY floorplan_lovelace.py /app/floorplan_lovelace.py
COPY floorplan_publisher.py /app/floorplan_publisher.py
COPY lab_virtual.py /app/lab_virtual.py
COPY lab_devices.py /app/lab_devices.py
COPY lab_dashboard.py /app/lab_dashboard.py
COPY bus_recorder.py /app/bus_recorder.py
COPY project_sessions.py /app/project_sessions.py
COPY project_ui.js /app/project_ui.js
COPY real_ui.js /app/real_ui.js
COPY recovery_ui.js /app/recovery_ui.js
COPY knx_history.py /app/knx_history.py
WORKDIR /app
CMD ["/command/with-contenv", "python3", "-u", "/app/bridge.py"]



COPY installation_review.py /app/installation_review.py

COPY commissioning.py /app/commissioning.py

COPY control_features.py /app/control_features.py
COPY control-diagrams.js /app/control-diagrams.js
COPY control-diagrams.css /app/control-diagrams.css

COPY control-visuals.js /app/control-visuals.js
COPY control-theme.css /app/control-theme.css

COPY control-templates.js /app/control-templates.js

COPY control-pipes.js /app/control-pipes.js

COPY control-technical.js /app/control-technical.js
COPY diagram_publisher.py /app/diagram_publisher.py

COPY nm-floorplan-card.js /app/nm-floorplan-card.js
