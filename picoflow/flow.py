"""PicoFlow Flow — directed graph runner with hooks and checkpointing.

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
Enable with checkpoint_dir:

    flow = Flow(start=node, checkpoint_dir="/tmp/run_42")

The store is snapshotted to JSON after every node completes.  If the process
crashes, restore and resume:

    store = Store.restore("/tmp/run_42/step_003_ExecuteSPLNode.json")
    flow.run(store, resume_from=execute_node)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from picoflow.node import Node
from picoflow.store import Store

_log = logging.getLogger("picoflow.flow")

# Hook event names
_VALID_HOOKS = {"node_start", "node_end", "node_error", "flow_end"}


class Flow:
    """Execute a directed graph of Nodes against a shared Store.

    Parameters
    ----------
    start :
        The first Node to run.
    checkpoint_dir :
        If set, snapshot the store after each node to this directory.
        Filenames are  step_<NNN>_<NodeName>.json .
    max_steps :
        Safety limit — raise RuntimeError if the graph runs longer than this.
        Default 100.  Prevents infinite loops from misconfigured cycles.

    Example
    -------
    >>> store = Store({"user_input": "hello"})
    >>> flow = Flow(start=my_node)
    >>> flow.on("node_end", lambda name, action, elapsed, s: print(f"{name} → {action}"))
    >>> flow.run(store)
    """

    def __init__(
        self,
        start: Node,
        checkpoint_dir: str | Path | None = None,
        max_steps: int = 100,
    ):
        self.start = start
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.max_steps = max_steps
        self._hooks: dict[str, list[Callable]] = {k: [] for k in _VALID_HOOKS}

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
        store: Store | dict,
        resume_from: Node | None = None,
    ) -> Store:
        """Run the flow until it terminates.  Returns the (mutated) store.

        Parameters
        ----------
        store :
            A Store instance or plain dict.  If a dict is passed, it is
            wrapped in a Store automatically (for backward compatibility).
        resume_from :
            If set, start from this node instead of self.start.  Use after
            restoring a checkpoint to skip already-completed nodes.
        """
        if isinstance(store, dict):
            store = Store(data=store)

        current: Node | None = resume_from or self.start
        step = 0
        flow_t0 = time.time()

        _log.info(
            "Flow starting  start=%s  checkpoint=%s",
            current.name if current else "none",
            str(self.checkpoint_dir) if self.checkpoint_dir else "off",
        )

        while current is not None:
            if step >= self.max_steps:
                raise RuntimeError(
                    f"Flow exceeded max_steps={self.max_steps}. "
                    "Check for infinite loops or increase max_steps."
                )

            self._fire("node_start", current.name, store)
            node_t0 = time.time()

            try:
                action = current._run(store)
            except Exception as exc:
                self._fire("node_error", current.name, exc, store)
                _log.error("Flow aborted at node '%s': %s", current.name, exc)
                raise

            elapsed = time.time() - node_t0
            self._fire("node_end", current.name, action, elapsed, store)

            # Optional checkpoint after every successful node
            if self.checkpoint_dir:
                ckpt = self.checkpoint_dir / f"step_{step:03d}_{current.name}.json"
                store.snapshot(ckpt)

            step += 1
            current = current.next_node(action)

        total_elapsed = time.time() - flow_t0
        _log.info(
            "Flow complete  steps=%d  total=%.2fs", step, total_elapsed
        )
        self._fire("flow_end", step, store)
        return store
