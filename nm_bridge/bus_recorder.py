"""Opt-in passive KNX event recorder. Never reads or writes group values."""
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from .dashboard_publisher import HAWebSocket
except ImportError:
    from dashboard_publisher import HAWebSocket


def addresses(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError("Indica da 1 a 32 indirizzi di gruppo")
    for ga in value:
        if not isinstance(ga, str) or not re.fullmatch(r"\d{1,2}/\d/\d{1,3}", ga):
            raise ValueError("Indirizzo di gruppo non valido")
        if any(n > limit for n, limit in zip(map(int, ga.split('/')), (31, 7, 255))):
            raise ValueError("Indirizzo di gruppo fuori intervallo")
    return sorted(set(value))


class Recorder:
    def __init__(self, path, client_factory=HAWebSocket):
        self.path = Path(path)
        self.factory = client_factory
        self.lock = threading.RLock()
        self.thread = None
        self.stop_event = threading.Event()
        self.status = "stopped"
        self.selected = []

    @contextmanager
    def _db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, destination TEXT, payload TEXT)")
                columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
                if 'received' not in columns:
                    db.execute("ALTER TABLE events ADD COLUMN received REAL NOT NULL DEFAULT 0")
                    for event_id, payload in db.execute("SELECT id,payload FROM events").fetchall():
                        try:
                            received = datetime.fromisoformat(json.loads(payload)['received_at']).timestamp()
                        except (ValueError, TypeError, KeyError):
                            received = 0
                        db.execute("UPDATE events SET received=? WHERE id=?", (received,event_id))
                    db.execute("CREATE INDEX IF NOT EXISTS events_received ON events(received)")
                yield db
        finally:
            db.close()

    def record(self, event):
        data = event.get("data", {})
        if not isinstance(data, dict) or data.get("destination") not in self.selected:
            return
        row = {key: data.get(key) for key in ("source", "destination", "direction", "telegramtype", "data", "value")}
        row["timestamp"] = event.get("time_fired")
        row["received_at"] = datetime.now(timezone.utc).isoformat()
        encoded = json.dumps(row, ensure_ascii=False)
        if len(encoded) > 4096:
            return
        with self._db() as db:
            db.execute("INSERT INTO events(destination,payload,received) VALUES (?,?,?)", (row["destination"], encoded, datetime.fromisoformat(row["received_at"]).timestamp()))
            db.execute("DELETE FROM events WHERE received < ?", ((datetime.now(timezone.utc)-timedelta(hours=48)).timestamp(),))
            db.execute("DELETE FROM events WHERE id <= (SELECT MAX(id)-10000 FROM events)")

    def snapshot(self, ga=None, source=None, start=None, end=None, before=None):
        def instant(value):
            if not value: return None
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None: raise ValueError('Indica il fuso orario')
            return parsed.timestamp()
        lower, upper = instant(start), instant(end)
        if lower is not None and upper is not None and lower > upper:
            raise ValueError('Intervallo temporale invertito')
        with self.lock:
            with self._db() as db:
                cutoff = (datetime.now(timezone.utc)-timedelta(hours=48)).timestamp()
                db.execute("DELETE FROM events WHERE received < ?", (cutoff,))
                clauses, args = [], []
                if ga: clauses.append('destination=?'); args.append(ga)
                if source: clauses.append("json_extract(payload,'$.source')=?"); args.append(source)
                if lower is not None: clauses.append('received>=?'); args.append(lower)
                if upper is not None: clauses.append('received<=?'); args.append(upper)
                if before is not None:
                    cursor = int(before)
                    if cursor < 1: raise ValueError('Cursore non valido')
                    clauses.append('id<?'); args.append(cursor)
                where = ' WHERE '+' AND '.join(clauses) if clauses else ''
                rows = db.execute('SELECT id,payload FROM events'+where+' ORDER BY id DESC LIMIT 501', args).fetchall()
                items = [json.loads(row[1]) for row in rows[:500]]
            return {"status": self.status, "addresses": self.selected[:], "items": items,
                    "next_cursor": rows[499][0] if len(rows)>500 else None,
                    "knx_traffic": False, "limit": 10000, "retention_hours": 48,
                    "note": "Eventi osservati da HA, non prova di consegna. Finestra massima 48 ore dalla ricezione, fino a 10000 eventi: con traffico elevato la copertura può essere inferiore. Pagina di 500 eventi. Dopo un riavvio riattivare la registrazione."}

    def start(self, payload):
        if not isinstance(payload, dict) or payload.get("confirm") is not True:
            raise ValueError("Conferma della registrazione obbligatoria")
        selected = addresses(payload.get("addresses"))
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("Arresta prima la registrazione corrente")
            self.selected = selected
            self.stop_event.clear()
            self.status = "connecting"
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        return self.snapshot()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.status = "stopping"
        return self.snapshot()

    def _run(self):
        # HA filter registration does not send KNX telegrams. Do not unregister
        # shared addresses on stop: other automations may depend on them.
        try:
            with self.factory() as client:
                client.call("subscribe_events", event_type="knx_event")
                try:
                    client.call("call_service", domain="knx", service="event_register",
                                service_data={"address": self.selected})
                    state = "listening"
                except ValueError:
                    state = "listening_existing: registra i GA in HA > Strumenti per sviluppatori > Azioni > KNX Register knx_event (amministratore)"
                client.connection.settimeout(1)
                self.status = state
                while not self.stop_event.is_set():
                    try:
                        message = client._receive()
                    except Exception as exc:
                        if isinstance(exc, TimeoutError) or type(exc).__name__ == "WebSocketTimeoutException":
                            continue
                        raise
                    if message.get("type") == "event":
                        self.record(message.get("event", {}))
            self.status = "stopped"
        except Exception:
            self.status = "error: connessione HA interrotta o registrazione KNX rifiutata; riavvia la registrazione"
