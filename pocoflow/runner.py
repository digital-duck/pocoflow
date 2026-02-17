"""PocoFlow Runner — background thread execution and run handle.

Usage
-----
    flow = Flow(start=my_node, db_path="pocoflow.db", flow_name="my_pipeline")
    handle = flow.run_background(store)

    # returns immediately; flow runs in a daemon thread
    print(handle.status)        # "running"
    print(handle.run_id)        # e.g. "my_pipeline-3f9a1b2c"

    result = handle.wait(timeout=60)   # block until done; returns Store
    print(handle.status)        # "completed"

    # cancel a running flow (cooperative — checked between nodes)
    handle.cancel()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pocoflow.db import WorkflowDB
    from pocoflow.store import Store

from pocoflow.logging import get_logger

_log = get_logger("runner")


class RunHandle:
    """Handle for a flow running in a background thread.

    Returned by :meth:`Flow.run_background`.  Do not instantiate directly.

    Attributes
    ----------
    run_id :
        Unique identifier for this run (matches the pf_runs.run_id if a db is
        configured).
    """

    def __init__(
        self,
        run_id: str,
        thread: threading.Thread,
        done_event: threading.Event,
        result_box: list,
        cancel_event: threading.Event,
        db: "WorkflowDB | None" = None,
    ):
        self.run_id = run_id
        self._thread = thread
        self._done = done_event
        self._result_box = result_box   # list[Store | Exception], len 1 when done
        self._cancel = cancel_event
        self._db = db

    # ── Status ────────────────────────────────────────────────────────────────

    @property
    def status(self) -> str:
        """Live status string.

        If a database is configured, reads from ``pf_runs.status`` (updated
        after every node).  Otherwise infers from thread state.

        Returns one of: ``"queued"`` | ``"running"`` | ``"paused"`` |
        ``"completed"`` | ``"failed"``.
        """
        if self._db is not None:
            run = self._db.get_run(self.run_id)
            if run:
                return run["status"]

        # Fallback: thread-based inference
        if not self._done.is_set():
            return "running"
        result = self._result_box[0] if self._result_box else None
        return "failed" if isinstance(result, Exception) else "completed"

    @property
    def is_done(self) -> bool:
        """True if the flow has finished (completed or failed)."""
        return self._done.is_set()

    # ── Control ───────────────────────────────────────────────────────────────

    def wait(self, timeout: float | None = None) -> "Store":
        """Block until the flow finishes and return the final Store.

        Parameters
        ----------
        timeout :
            Maximum seconds to wait.  ``None`` waits indefinitely.

        Raises
        ------
        TimeoutError
            If *timeout* elapses before the flow completes.
        Exception
            Re-raises any exception the flow raised internally.
        """
        finished = self._done.wait(timeout=timeout)
        if not finished:
            raise TimeoutError(
                f"Flow run '{self.run_id}' did not complete within {timeout}s"
            )
        result = self._result_box[0]
        if isinstance(result, Exception):
            raise result
        return result

    def cancel(self) -> None:
        """Request cancellation.

        Sets a flag that Flow checks between nodes.  The flow will stop after
        the current node finishes (not mid-execution).  The run status is set
        to ``"failed"`` with ``error_msg="cancelled"``.
        """
        _log.info("Cancel requested for run '%s'", self.run_id)
        self._cancel.set()
