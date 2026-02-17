"""PocoFlow logging — thin wrapper around dd-logging for consistent log format.

Usage
-----
In every pocoflow module:
    from pocoflow.logging import get_logger
    _log = get_logger("node")   # → pocoflow.node logger

To initialise file logging at application start-up:
    from pocoflow.logging import setup_logging
    setup_logging("my_run", log_level="debug")
    # → logs/my_run-<YYYYMMDD-HHMMSS>.log under pocoflow.*

Log hierarchy
-------------
    pocoflow              ← root (FileHandler attached by setup_logging)
    ├── pocoflow.store
    ├── pocoflow.node
    ├── pocoflow.flow
    ├── pocoflow.db
    └── pocoflow.runner
"""

from __future__ import annotations

import logging
from pathlib import Path

from dd_logging import (
    disable_logging as _disable,
    get_logger as _get,
    setup_logging as _setup,
)

_ROOT = "pocoflow"


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the pocoflow namespace.

    Parameters
    ----------
    name :
        Dotted sub-path, e.g. ``"node"`` → ``pocoflow.node``.
    """
    return _get(name, _ROOT)


def setup_logging(
    run_name: str = "pocoflow",
    *,
    log_level: str = "info",
    log_dir: str | Path | None = None,
    console: bool = False,
    adapter: str = "",
) -> Path:
    """Attach a timestamped FileHandler to the pocoflow root logger.

    Parameters
    ----------
    run_name :
        Short label used in the log filename, e.g. ``"run"`` or ``"benchmark"``.
    log_level :
        ``"debug"`` | ``"info"`` | ``"warning"`` | ``"error"``.
    log_dir :
        Directory for log files.  Defaults to ``./logs`` relative to CWD.
    console :
        Also attach a StreamHandler (useful for CLI --verbose mode).
    adapter :
        LLM adapter name appended to the filename (e.g. ``"openrouter"``).

    Returns
    -------
    Path
        Absolute path of the created log file.
    """
    return _setup(
        run_name,
        root_name=_ROOT,
        log_level=log_level,
        log_dir=log_dir or (Path.cwd() / "logs"),
        console=console,
        adapter=adapter,
    )


def disable_logging() -> None:
    """Remove all handlers from the pocoflow root logger (silent mode)."""
    _disable(_ROOT)
