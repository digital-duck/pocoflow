"""PicoFlow DB — SQLite backend for workflow runs, checkpoints, and events.

Schema
------
Three tables live in a single SQLite file:

  pf_runs        — one row per flow execution (run_id, status, timing)
  pf_checkpoints — Store snapshot after each node (step, store_json)
  pf_events      — ordered event log (flow_start, node_start/end/error, flow_end)

Thread-safety: each method opens its own sqlite3 connection — no shared
connection state, so concurrent readers and the background runner thread are safe.

WAL mode is enabled on first connection so UI polling doesn't block writes.

Usage
-----
    from picoflow.db import WorkflowDB

    db = WorkflowDB("picoflow.db")
    db.create_run("run-abc", flow_name="my_pipeline")
    db.save_event("run-abc", "flow_start", node_name="StepA", ts=now())
    # ... after each node ...
    db.save_checkpoint("run-abc", step=0, node_name="StepA", store=store)
    db.update_run("run-abc", status="completed")

    runs = db.list_runs()
    store = db.load_checkpoint("run-abc", step=0)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from picoflow.logging import get_logger
from picoflow.store import Store

_log = get_logger("db")

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pf_runs (
    run_id       TEXT PRIMARY KEY,
    flow_name    TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ('queued','running','paused','completed','failed')),
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    total_steps  INTEGER,
    current_node TEXT,
    error_msg    TEXT
);

CREATE TABLE IF NOT EXISTS pf_checkpoints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    step        INTEGER NOT NULL,
    node_name   TEXT NOT NULL,
    store_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(run_id, step),
    FOREIGN KEY (run_id) REFERENCES pf_runs(run_id)
);

CREATE TABLE IF NOT EXISTS pf_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    step        INTEGER,
    node_name   TEXT,
    event       TEXT NOT NULL,
    action      TEXT,
    elapsed_ms  REAL,
    error_msg   TEXT,
    ts          TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES pf_runs(run_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowDB:
    """SQLite-backed store for PicoFlow workflow observability.

    Parameters
    ----------
    db_path :
        Path to the SQLite file.  Created (with parent directories) if it does
        not exist.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DDL)
        _log.debug("WorkflowDB ready  path=%s", self.db_path)

    # ── Run management ────────────────────────────────────────────────────────

    def create_run(self, run_id: str, flow_name: str = "") -> None:
        """Insert a new run record with status='running'."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO pf_runs (run_id, flow_name, started_at) VALUES (?,?,?)",
                (run_id, flow_name, _now()),
            )
        _log.debug("Run created  run_id=%s  flow=%s", run_id, flow_name)

    def update_run(self, run_id: str, **fields: Any) -> None:
        """Update arbitrary fields on a run row.

        Allowed fields: status, completed_at, total_steps, current_node, error_msg.
        """
        allowed = {"status", "completed_at", "total_steps", "current_node", "error_msg"}
        cols = {k: v for k, v in fields.items() if k in allowed}
        if not cols:
            return
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE pf_runs SET {set_clause} WHERE run_id = ?",
                (*cols.values(), run_id),
            )

    def get_run(self, run_id: str) -> dict | None:
        """Return a single run row as a dict, or None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pf_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 100) -> list[dict]:
        """Return the most-recent runs ordered by started_at DESC."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pf_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Checkpoints ───────────────────────────────────────────────────────────

    def save_checkpoint(
        self,
        run_id: str,
        step: int,
        node_name: str,
        store: Store,
    ) -> None:
        """Persist a Store snapshot after a node completes.

        Uses INSERT OR REPLACE so re-running the same step (e.g. after retry)
        overwrites the previous checkpoint.
        """
        safe: dict[str, Any] = {}
        for k, v in store._data.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = f"<non-serialisable: {type(v).__name__}>"
        store_json = json.dumps(safe, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pf_checkpoints
                   (run_id, step, node_name, store_json, created_at)
                   VALUES (?,?,?,?,?)""",
                (run_id, step, node_name, store_json, _now()),
            )
        _log.debug("Checkpoint saved  run=%s  step=%d  node=%s", run_id, step, node_name)

    def get_checkpoints(self, run_id: str) -> list[dict]:
        """Return all checkpoints for a run ordered by step."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pf_checkpoints WHERE run_id=? ORDER BY step",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def load_checkpoint(self, run_id: str, step: int) -> Store:
        """Reconstruct a Store from a saved checkpoint.

        Raises
        ------
        KeyError
            If no checkpoint exists for (run_id, step).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT store_json FROM pf_checkpoints WHERE run_id=? AND step=?",
                (run_id, step),
            ).fetchone()
        if row is None:
            raise KeyError(f"No checkpoint for run_id={run_id!r} step={step}")
        data = json.loads(row["store_json"])
        return Store(data=data, name=f"{run_id}@step{step}")

    # ── Events ────────────────────────────────────────────────────────────────

    def save_event(self, run_id: str, event: str, **kw: Any) -> None:
        """Append a lifecycle event.

        Keyword args (all optional):
          step, node_name, action, elapsed_ms, error_msg, ts
        """
        ts = kw.pop("ts", _now())
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO pf_events
                   (run_id, event, step, node_name, action, elapsed_ms, error_msg, ts)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run_id, event,
                    kw.get("step"),
                    kw.get("node_name"),
                    kw.get("action"),
                    kw.get("elapsed_ms"),
                    kw.get("error_msg"),
                    ts,
                ),
            )

    def get_events(self, run_id: str) -> list[dict]:
        """Return all events for a run ordered by insertion id."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pf_events WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]
