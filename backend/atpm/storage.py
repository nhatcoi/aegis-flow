import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def database():
    path = Path(os.environ.get("ATPM_DB", ROOT / "data/lab.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize():
    with database() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts (hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, spec_hash TEXT NOT NULL REFERENCES artifacts(hash),
                state TEXT NOT NULL, seen TEXT NOT NULL, enforce INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
                payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        default = json.loads((ROOT / "specs/payment.json").read_text())
        db.execute("INSERT OR IGNORE INTO project(id, payload) VALUES(1, ?)", (json.dumps(default),))


def read_run(db, run_id):
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "spec_hash": row["spec_hash"], "state": json.loads(row["state"]),
            "enforce": bool(row["enforce"]), "created_at": row["created_at"],
            "events": [dict(json.loads(item["payload"]), timestamp=item["created_at"])
                       for item in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,))]}
