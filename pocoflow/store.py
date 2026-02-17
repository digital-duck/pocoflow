"""PocoFlow Store — typed, observable, checkpointable shared state.

Fixes PocketFlow weakness #1: raw dict with no type safety or schema.

Design
------
Store wraps a plain dict but adds:
  • schema    — declares required keys and their types at construction time
  • get/set   — type-checked access with clear KeyError / TypeError messages
  • observers — callbacks fired on every write  (for logging / tracing)
  • snapshot  — serialise current state to JSON  (for checkpointing)
  • restore   — deserialise from JSON            (for crash recovery)

Store is deliberately still dict-like so existing code migrates with minimal
friction:  store["key"] = value  and  store["key"]  still work.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pocoflow.logging import get_logger

_log = get_logger("store")


class Store:
    """Shared state container for a PocoFlow pipeline run.

    Parameters
    ----------
    data :
        Initial key-value pairs.
    schema :
        Optional dict mapping key → type (or tuple of types).
        Keys listed here are *required* — `validate()` raises if any are
        missing.  Values are type-checked on every write when schema is set.
    name :
        Human-readable label shown in log messages and snapshots.

    Examples
    --------
    >>> store = Store(
    ...     data={"user_input": "", "adapter": "claude_cli"},
    ...     schema={"user_input": str, "adapter": str},
    ...     name="spl_pipeline",
    ... )
    >>> store["user_input"] = "explain quantum entanglement"
    >>> store.snapshot("/tmp/checkpoint.json")
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        schema: dict[str, type | tuple] | None = None,
        name: str = "store",
    ):
        self._data: dict[str, Any] = dict(data or {})
        self._schema: dict[str, type | tuple] = schema or {}
        self._name = name
        self._observers: list[Callable[[str, Any, Any], None]] = []

    # ── dict-like access ──────────────────────────────────────────────────────

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._schema:
            expected = self._schema[key]
            if not isinstance(value, expected):
                raise TypeError(
                    f"Store[{self._name}]: key '{key}' expects "
                    f"{expected}, got {type(value).__name__}"
                )
        old = self._data.get(key)
        self._data[key] = value
        for obs in self._observers:
            try:
                obs(key, old, value)
            except Exception as e:
                _log.warning("Store observer error: %s", e)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def update(self, mapping: dict[str, Any]) -> None:
        for k, v in mapping.items():
            self[k] = v

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __repr__(self) -> str:
        return f"Store(name={self._name!r}, keys={list(self._data.keys())})"

    # ── schema validation ─────────────────────────────────────────────────────

    def validate(self) -> None:
        """Raise ValueError if any schema-required key is missing."""
        missing = [k for k in self._schema if k not in self._data]
        if missing:
            raise ValueError(
                f"Store[{self._name}]: required key(s) missing: {missing}"
            )

    # ── observers (for logging / tracing) ─────────────────────────────────────

    def add_observer(self, callback: Callable[[str, Any, Any], None]) -> None:
        """Register callback(key, old_value, new_value) fired on every write."""
        self._observers.append(callback)

    def remove_observer(self, callback: Callable) -> None:
        self._observers = [o for o in self._observers if o is not callback]

    # ── checkpointing ─────────────────────────────────────────────────────────

    def snapshot(self, path: str | Path) -> None:
        """Serialise the store to a JSON file for crash recovery."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert non-serialisable values to strings with a warning
        safe: dict[str, Any] = {}
        for k, v in self._data.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = f"<non-serialisable: {type(v).__name__}>"
                _log.debug("Store snapshot: key '%s' is not JSON-serialisable, stored as string", k)

        payload = {"name": self._name, "data": safe}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        _log.debug("Store snapshot saved → %s", path)

    @classmethod
    def restore(cls, path: str | Path, schema: dict | None = None) -> "Store":
        """Deserialise a store from a JSON snapshot file."""
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        store = cls(data=payload["data"], schema=schema, name=payload.get("name", "store"))
        _log.debug("Store restored ← %s", path)
        return store

    # ── convenience: expose raw dict for PocketFlow-compat code ──────────────

    def as_dict(self) -> dict[str, Any]:
        """Return the underlying dict (no copy — modifications are reflected)."""
        return self._data
