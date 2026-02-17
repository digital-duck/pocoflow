"""PicoFlow Node — the nano-ETL unit of every pipeline step.

Fixes PocketFlow weakness #2 (edge API) and #3 (async).

Design
------
Every Node is a three-phase processing unit:

    prep(store)              → Extract: read what this node needs from the store
    exec(prep_result)        → Transform: do the work (pure, no store side-effects)
    post(store, prep, exec)  → Load: write results back, return next action string

This maps directly to ETL:
    E → prep    (read inputs)
    T → exec    (compute)
    L → post    (write outputs + route)

Edge wiring uses a single, unambiguous API:
    node.then("action", next_node)   — named edge (always explicit)
    node.then("*", fallback_node)    — wildcard: matches any unhandled action

No more `>>` shorthand that silently creates "default" edges and causes
UserWarning mismatches.

AsyncNode subclasses override exec_async() instead of exec(); the base class
calls it via asyncio.run() so the rest of the framework stays synchronous.
Nodes that need true concurrency should use asyncio.gather() inside exec_async().

Retry
-----
Set max_retries > 1 on any Node to automatically retry exec() on exception.
The node is NOT re-run from prep() — only exec() is retried.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from picoflow.logging import get_logger

_log = get_logger("node")

DEFAULT_ACTION = "default"
WILDCARD_ACTION = "*"


class Node(ABC):
    """Base class for all synchronous PicoFlow nodes.

    Subclass and implement at minimum exec().

    Attributes
    ----------
    max_retries :
        How many times to attempt exec() before raising.  Default 1 (no retry).
    retry_delay :
        Seconds to wait between retries.  Default 0.
    """

    max_retries: int = 1
    retry_delay: float = 0.0

    def __init__(self):
        # action → Node mapping; populated by .then()
        self._successors: dict[str, "Node"] = {}
        self.name = self.__class__.__name__

    # ── Wiring API ────────────────────────────────────────────────────────────

    def then(self, action: str, node: "Node") -> "Node":
        """Wire this node to *node* when *action* is returned by post().

        Use "*" as action to match any action not covered by a named edge.

        Returns self so calls can be chained:
            a.then("ok", b).then("error", c)
        """
        if action in self._successors:
            _log.warning(
                "Node '%s': overwriting existing edge for action '%s'", self.name, action
            )
        self._successors[action] = node
        return self

    def next_node(self, action: str) -> "Node | None":
        """Return the successor for *action*, or None if the flow terminates."""
        node = self._successors.get(action)
        if node is None and WILDCARD_ACTION in self._successors:
            node = self._successors[WILDCARD_ACTION]
            _log.debug("Node '%s': action '%s' matched wildcard edge", self.name, action)
        if node is None and self._successors:
            _log.debug(
                "Node '%s': action '%s' has no successor → flow terminates here "
                "(available actions: %s)",
                self.name, action, list(self._successors.keys()),
            )
        return node

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def prep(self, store: Any) -> Any:
        """Extract inputs from the shared store.  Override as needed."""
        return None

    @abstractmethod
    def exec(self, prep_result: Any) -> Any:
        """Transform: do the actual work.  Must not write to the store."""

    def post(self, store: Any, prep_result: Any, exec_result: Any) -> str:
        """Load: write results to store and return the next action string."""
        return DEFAULT_ACTION

    # ── Internal runner (called by Flow) ─────────────────────────────────────

    def _run(self, store: Any) -> str:
        """Execute prep → exec (with retries) → post.  Return action string."""
        t0 = time.time()
        _log.info("→ Node '%s' starting", self.name)

        prep_result = self.prep(store)

        exec_result = None
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                exec_result = self.exec(prep_result)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    _log.warning(
                        "Node '%s' exec attempt %d/%d failed: %s — retrying in %.1fs",
                        self.name, attempt, self.max_retries, exc, self.retry_delay,
                    )
                    if self.retry_delay > 0:
                        time.sleep(self.retry_delay)
                else:
                    _log.error(
                        "Node '%s' exec failed after %d attempt(s): %s",
                        self.name, self.max_retries, exc,
                    )

        if last_exc is not None:
            raise last_exc

        action = self.post(store, prep_result, exec_result)
        elapsed = time.time() - t0
        _log.info("← Node '%s' done  action='%s'  %.2fs", self.name, action, elapsed)
        return action


class AsyncNode(Node, ABC):
    """Base class for nodes whose exec step is asynchronous.

    Subclass and implement exec_async() instead of exec().
    The framework calls exec_async() via asyncio.run() so the surrounding
    Flow stays synchronous.  Use asyncio.gather() inside exec_async() for
    true parallel sub-tasks.

    Example
    -------
    class FetchNode(AsyncNode):
        async def exec_async(self, urls):
            results = await asyncio.gather(*[fetch(u) for u in urls])
            return results
    """

    @abstractmethod
    async def exec_async(self, prep_result: Any) -> Any:
        """Async transform step.  Implement this instead of exec()."""

    def exec(self, prep_result: Any) -> Any:
        """Runs exec_async() on a new event loop.  Do not override."""
        return asyncio.run(self.exec_async(prep_result))
