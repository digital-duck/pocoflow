"""PicoFlow Flow — directed graph runner with hooks, checkpointing, and observability.

Fixes PocketFlow weaknesses #4 (no observability) and #5 (no checkpointing).

Design
------
Flow takes a start Node and runs the graph by:
  1. Calling node._run(store) → action string
  2. Looking up node.next_node(action) → next Node or None
  3. Repeating until next Node is None (flow terminates naturally)

Hooks (observability)
---------------------
Register callbacks for key lifecycle events:

    flow.on("node_start",  lambda name, store: ...)
    flow.on("node_end",    lambda name, action, elapsed, store: ...)
    flow.on("node_error",  lambda name, exc, store: ...)
    flow.on("flow_end",    lambda steps, store: ...)

These are thin wrappers — no framework-specific objects, just plain Python
callables.  Wire them to your logger, a metrics sink, or a UI progress bar.

Checkpointing
-------------
JSON checkpoints (backward-compatible):

    flow = Flow(start=node, checkpoint_dir="/tmp/run_42")

SQLite checkpoints (queryable, concurrent-safe):

    flow = Flow(start=node, db_path="picoflow.db", flow_name="my_pipeline")

Both can be enabled simultaneously.

Background execution
--------------------
For long-running workflows, start in a daemon thread and get back a RunHandle:

    handle = flow.run_background(store)
    print(handle.status)          # "running"
    result = handle.wait(timeout=120)
    print(handle.status)          # "completed"

    # Cooperative cancel (stops between nodes)
    handle.cancel()

Resume after crash
------------------
    store = Store.restore("/tmp/run_42/step_003_ExecuteSPLNode.json")
    flow.run(store, resume_from=execute_node)

    # or from SQLite checkpoint:
    from picoflow.db import WorkflowDB
    db = WorkflowDB("picoflow.db")
    store = db.load_checkpoint(run_id, step=3)
    flow.run(store, resume_from=execute_node)
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from picoflow.logging import get_logger
from picoflow.node import Node
from picoflow.store import Store

_log = get_logger("flow")

# Hook event names
_VALID_HOOKS = {"node_start", "node_end", "node_error", "flow_end"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Flow:
    """Execute a directed graph of Nodes against a shared Store.

    Parameters
    ----------
    start :
        The first Node to run.
    checkpoint_dir :
        If set, snapshot the store to JSON after each node.
        Filenames: ``step_<NNN>_<NodeName>.json``.
    max_steps :
        Safety limit — raise RuntimeError if the graph runs longer than this.
        Default 100.  Prevents infinite loops from misconfigured cycles.
    db_path :
        If set, persist run metadata, events, and checkpoints to SQLite.
        Enables the Streamlit monitor and ``run_background()``.
    run_id :
        Explicit run identifier.  Auto-generated (``<flow_name>-<uuid8>``) if
        not provided.
    flow_name :
        Human-readable label shown in the monitor UI and log messages.

    Example
    -------
    >>> store = Store({"user_input": "hello"})
    >>> flow = Flow(start=my_node, db_path="picoflow.db", flow_name="demo")
    >>> flow.on("node_end", lambda name, action, elapsed, s: print(f"{name} → {action}"))
    >>> flow.run(store)

    >>> handle = flow.run_background(store)
    >>> handle.wait()
    """

    def __init__(
        self,
        start: Node,
        checkpoint_dir: str | Path | None = None,
        max_steps: int = 100,
        db_path: str | Path | None = None,
        run_id: str | None = None,
        flow_name: str | None = None,
    ):
        self.start = start
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.max_steps = max_steps
        self.db_path = Path(db_path) if db_path else None
        self.run_id = run_id
        self.flow_name = flow_name or start.__class__.__name__
        self._hooks: dict[str, list[Callable]] = {k: [] for k in _VALID_HOOKS}
        self._cancel_event: threading.Event | None = None

        if self.checkpoint_dir:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # ── Hook registration ─────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> "Flow":
        """Register *callback* for *event*.  Returns self for chaining.

        Events and callback signatures
        --------------------------------
        node_start  (node_name: str, store: Store)
        node_end    (node_name: str, action: str, elapsed_s: float, store: Store)
        node_error  (node_name: str, exc: Exception, store: Store)
        flow_end    (total_steps: int, store: Store)
        """
        if event not in _VALID_HOOKS:
            raise ValueError(f"Unknown hook event '{event}'. Valid: {_VALID_HOOKS}")
        self._hooks[event].append(callback)
        return self

    def _fire(self, event: str, *args) -> None:
        for cb in self._hooks[event]:
            try:
                cb(*args)
            except Exception as e:
                _log.warning("Hook '%s' raised: %s", event, e)

    # ── Execution ─────────────────────────────────────────────────────────────

    def run(
        self,
        store: "Store | dict",
        resume_from: Node | None = None,
    ) -> Store:
        """Run the flow until it terminates.  Returns the (mutated) store.

        Parameters
        ----------
        store :
            A Store instance or plain dict.  If a dict is passed, it is
            wrapped in a Store automatically.
        resume_from :
            If set, start from this node instead of self.start.  Use after
            restoring a checkpoint to skip already-completed nodes.
        """
        if isinstance(store, dict):
            store = Store(data=store)

        # ── DB setup ──────────────────────────────────────────────────────────
        db = None
        run_id: str | None = None
        if self.db_path:
            from picoflow.db import WorkflowDB
            db = WorkflowDB(self.db_path)
            run_id = self.run_id or f"{self.flow_name}-{uuid4().hex[:8]}"
            self._run_id = run_id
            db.create_run(run_id, self.flow_name)

        current: Node | None = resume_from or self.start
        step = 0
        flow_t0 = time.time()

        _log.info(
            "Flow starting  name=%s  run_id=%s  start=%s  db=%s  ckpt=%s",
            self.flow_name,
            run_id or "—",
            current.name if current else "none",
            str(self.db_path) if self.db_path else "off",
            str(self.checkpoint_dir) if self.checkpoint_dir else "off",
        )

        if db and run_id:
            db.save_event(run_id, "flow_start",
                          node_name=current.name if current else "", ts=_now())

        while current is not None:
            # ── Cancel check ──────────────────────────────────────────────────
            if self._cancel_event and self._cancel_event.is_set():
                _log.info("Flow '%s' cancelled at node '%s'", self.flow_name, current.name)
                if db and run_id:
                    db.update_run(run_id, status="failed",
                                  error_msg="cancelled", completed_at=_now())
                break

            if step >= self.max_steps:
                raise RuntimeError(
                    f"Flow exceeded max_steps={self.max_steps}. "
                    "Check for infinite loops or increase max_steps."
                )

            # ── Update current node in DB ──────────────────────────────────────
            if db and run_id:
                db.update_run(run_id, current_node=current.name)
                db.save_event(run_id, "node_start",
                              step=step, node_name=current.name, ts=_now())

            self._fire("node_start", current.name, store)
            node_t0 = time.time()

            try:
                action = current._run(store)
            except Exception as exc:
                self._fire("node_error", current.name, exc, store)
                _log.error("Flow '%s' aborted at node '%s': %s",
                           self.flow_name, current.name, exc)
                if db and run_id:
                    db.save_event(run_id, "node_error",
                                  step=step, node_name=current.name,
                                  error_msg=str(exc), ts=_now())
                    db.update_run(run_id, status="failed",
                                  error_msg=str(exc), completed_at=_now())
                raise

            elapsed = time.time() - node_t0
            self._fire("node_end", current.name, action, elapsed, store)

            if db and run_id:
                db.save_event(run_id, "node_end",
                              step=step, node_name=current.name,
                              action=action, elapsed_ms=elapsed * 1000, ts=_now())
                db.save_checkpoint(run_id, step, current.name, store)
                db.update_run(run_id, total_steps=step + 1)

            # JSON checkpoint (backward-compatible)
            if self.checkpoint_dir:
                ckpt = self.checkpoint_dir / f"step_{step:03d}_{current.name}.json"
                store.snapshot(ckpt)

            step += 1
            current = current.next_node(action)

        total_elapsed = time.time() - flow_t0
        _log.info("Flow '%s' complete  steps=%d  total=%.2fs",
                  self.flow_name, step, total_elapsed)
        self._fire("flow_end", step, store)

        if db and run_id:
            db.save_event(run_id, "flow_end", step=step, ts=_now())
            # Only mark completed if not already failed/cancelled
            run = db.get_run(run_id)
            if run and run["status"] == "running":
                db.update_run(run_id, status="completed",
                              completed_at=_now(), total_steps=step)

        return store

    # ── Background execution ──────────────────────────────────────────────────

    def run_background(
        self,
        store: "Store | dict",
        resume_from: Node | None = None,
    ) -> "RunHandle":
        """Start the flow in a daemon thread and return a RunHandle immediately.

        The RunHandle lets you poll status, block until done, or cancel.

        Parameters
        ----------
        store :
            A Store instance or plain dict.
        resume_from :
            Optional node to start from (checkpoint resume).

        Returns
        -------
        RunHandle
            Handle to monitor and control the background run.

        Example
        -------
        >>> handle = flow.run_background(Store({"query": "..."}))
        >>> print(handle.status)   # "running"
        >>> result = handle.wait(timeout=120)
        >>> print(handle.status)   # "completed"
        """
        from picoflow.runner import RunHandle

        if isinstance(store, dict):
            store = Store(data=store)

        done_event = threading.Event()
        result_box: list = []
        cancel_event = threading.Event()
        self._cancel_event = cancel_event

        # Determine run_id before starting (so handle has it immediately)
        run_id = self.run_id or f"{self.flow_name}-{uuid4().hex[:8]}"
        self._run_id = run_id
        # Lock in the run_id so flow.run() reuses it (not regenerates)
        self.run_id = run_id

        def _target():
            try:
                final_store = self.run(store, resume_from=resume_from)
                result_box.append(final_store)
            except Exception as exc:
                result_box.append(exc)
            finally:
                done_event.set()

        thread = threading.Thread(target=_target, daemon=True, name=f"picoflow-{run_id}")
        thread.start()

        db = None
        if self.db_path:
            from picoflow.db import WorkflowDB
            db = WorkflowDB(self.db_path)

        _log.info("Flow '%s' started in background  run_id=%s", self.flow_name, run_id)

        return RunHandle(
            run_id=run_id,
            thread=thread,
            done_event=done_event,
            result_box=result_box,
            cancel_event=cancel_event,
            db=db,
        )
