"""Indexed, run-scoped causal event storage and read-only trace queries."""
import json
import sqlite3


class TraceStore:
    def __init__(self, directory):
        self.connection = sqlite3.connect(directory / "trace.sqlite")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, arm TEXT, vehicle TEXT, payload TEXT)")
        self.connection.execute("CREATE INDEX vehicle_events ON events(arm, vehicle, seq)")
        self.flush()

    def add(self, arm, event):
        vehicle = event.get("vehicle_id") or event.get("payload", {}).get("vehicle_id")
        self.connection.execute("INSERT INTO events(arm, vehicle, payload) VALUES(?,?,?)", (arm, vehicle, json.dumps(event)))

    def flush(self):
        self.connection.commit()

    def close(self):
        self.flush()
        self.connection.close()


def trace(directory, arm, vehicle, after=0):
    path = directory / "trace.sqlite"
    if not path.exists():
        return {"events": [], "vehicles": []}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT seq,payload FROM events WHERE arm=? AND vehicle=? AND seq>? ORDER BY seq LIMIT 1000", (arm, vehicle, after)).fetchall()
        vehicles = [row[0] for row in db.execute("SELECT DISTINCT vehicle FROM events WHERE arm=? AND vehicle IS NOT NULL ORDER BY vehicle LIMIT 2000", (arm,))]
    return {"events": [{"seq": seq, **json.loads(payload)} for seq, payload in rows], "vehicles": vehicles,
            "next_after": rows[-1][0] if rows else after, "has_more": len(rows) == 1000}

