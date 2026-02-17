# PocoFlow

> Lightweight LLM workflow orchestration.
> A hardened evolution of [PocketFlow](https://github.com/The-Pocket/PocketFlow).

Built with love by **Claude & digital-duck** 🦆

---

## What It Is

PocoFlow is a minimal framework for building LLM pipelines as **directed graphs of
nano-ETL nodes** communicating through a shared, typed Store.

It keeps PocketFlow's best idea — the `prep | exec | post` abstraction — and fixes
the weaknesses that surface in production:

| Weakness | PocoFlow fix |
|----------|-------------|
| Raw dict store — no type safety | `Store` with optional schema + `TypeError` on bad writes |
| Ambiguous `>>` edge API | Single clear API: `.then("action", next_node)` |
| No built-in async support | `AsyncNode.exec_async()` — framework handles `asyncio.run()` |
| No observability | Hook system: `node_start / node_end / node_error / flow_end` |
| No checkpointing | JSON snapshots + **SQLite backend** with full event log |
| No long-running support | `run_background()` → `RunHandle` with status, wait, cancel |
| Inconsistent logging | **dd-logging** integration — structured, file-backed, namespaced |
| No workflow visibility | **Streamlit monitor UI** — live runs table, timeline, store inspector |

**Dependencies:** [pocketflow](https://github.com/The-Pocket/PocketFlow) + [dd-logging](https://github.com/digital-duck/dd-logging)

---

## Install

```bash
# Core
pip install pocoflow

# With Streamlit monitor UI
pip install "pocoflow[ui]"

# Local dev (from the digital-duck monorepo)
pip install -e ~/projects/digital-duck/dd-logging
pip install -e ~/projects/digital-duck/pocoflow"[ui,dev]"
```

---

## Quick Start

```python
from pocoflow import Node, Flow, Store

class SummariseNode(Node):
    def prep(self, store):
        return store["document"]

    def exec(self, text):
        return llm.summarise(text)          # your LLM call here

    def post(self, store, prep, summary):
        store["summary"] = summary
        return "done"

store = Store({"document": "...", "summary": ""})
Flow(start=SummariseNode(), db_path="pocoflow.db", flow_name="summarise").run(store)
print(store["summary"])
```

Then open the monitor:

```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

---

## Core Concepts

### Node — nano-ETL

Every node is a three-phase processing unit that maps directly to **Extract → Transform → Load**:

```
prep(store)              → Extract:   read what this node needs from the store
exec(prep_result)        → Transform: do the work (pure — no store side-effects)
post(store, prep, exec)  → Load:      write results back, return next action string
```

| Phase | ETL step | Purity |
|-------|----------|--------|
| `prep` | Extract | reads store |
| `exec` | Transform | pure function — retryable, testable without a store |
| `post` | Load + Route | writes store, returns action string |

```python
from pocoflow import Node

class CallLLMNode(Node):
    max_retries = 3       # retry exec() automatically on failure
    retry_delay = 1.0     # seconds between retries

    def prep(self, store):
        return store["prompt"]

    def exec(self, prompt):
        return llm.call(prompt)   # retried up to 3× on exception

    def post(self, store, prep, response):
        store["response"] = response
        return "done"
```

### Store — typed shared state

```python
from pocoflow import Store

store = Store(
    data={"query": "", "result": ""},
    schema={"query": str, "result": str},   # type-checked on every write
    name="my_pipeline",
)
store["query"] = "explain quantum entanglement"
store["query"] = 42          # ← raises TypeError immediately

# Observer: fired on every write (logging, tracing, UI updates)
store.add_observer(lambda key, old, new: print(f"{key}: {old!r} → {new!r}"))

# JSON snapshot / restore (lightweight backup)
store.snapshot("/tmp/run_42/step_002.json")
store2 = Store.restore("/tmp/run_42/step_002.json")
```

### Flow — directed graph with hooks

```python
from pocoflow import Flow, Store

# Wire nodes with unambiguous named edges
a.then("ok",    b)
a.then("error", c)
a.then("*",     fallback)   # wildcard: matches any unhandled action

# Build with SQLite persistence
flow = Flow(
    start=a,
    flow_name="my_pipeline",    # label shown in the monitor UI
    db_path="pocoflow.db",      # SQLite: runs, events, checkpoints
    checkpoint_dir="/tmp/ckpt", # also write JSON snapshots (optional)
    max_steps=50,               # guard against infinite loops
)

# Hooks — wire to any logger, metrics sink, or progress bar
flow.on("node_start", lambda name, store: print(f"▶ {name}"))
flow.on("node_end",   lambda name, action, elapsed, store:
                          print(f"✓ {name} → {action}  ({elapsed:.2f}s)"))
flow.on("node_error", lambda name, exc, store: alert(name, exc))
flow.on("flow_end",   lambda steps, store: print(f"Done in {steps} steps"))

store = Store({"query": "..."})
flow.run(store)
```

### AsyncNode — parallel sub-tasks

```python
from pocoflow import AsyncNode
import asyncio

class FetchNode(AsyncNode):
    def prep(self, store):
        return store["urls"]

    async def exec_async(self, urls):
        return await asyncio.gather(*[fetch(u) for u in urls])

    def post(self, store, prep, results):
        store["pages"] = results
        return "done"
```

Implement `exec_async()` — the framework calls it via `asyncio.run()`.
Use `asyncio.gather()` inside for true parallel sub-tasks.

---

## SQLite Backend

When `db_path` is set, every run is fully recorded in a SQLite database:

```
pf_runs        — one row per flow execution (run_id, status, timing, error)
pf_checkpoints — Store snapshot after every node  (restorable at any step)
pf_events      — ordered event log (flow_start → node_start/end/error → flow_end)
```

```python
from pocoflow import WorkflowDB

db = WorkflowDB("pocoflow.db")

# List all runs
for run in db.list_runs():
    print(run["run_id"], run["status"], run["total_steps"])

# Inspect events for a run
for event in db.get_events("my_pipeline-3f9a1b2c"):
    print(event["event"], event["node_name"], event["elapsed_ms"])

# Restore Store from any checkpoint
store = db.load_checkpoint("my_pipeline-3f9a1b2c", step=2)
```

WAL mode is enabled so the Streamlit monitor can poll while a flow is running.

---

## Long-Running Workflows

For flows that take minutes or hours, use `run_background()` to avoid blocking:

```python
flow = Flow(start=my_node, db_path="pocoflow.db", flow_name="research")

# Returns immediately — flow runs in a daemon thread
handle = flow.run_background(store)

print(handle.run_id)          # e.g. "research-3f9a1b2c"
print(handle.status)          # "running"   (reads live from SQLite)

# Block until done (optional timeout)
result = handle.wait(timeout=300)
print(handle.status)          # "completed"

# Cooperative cancel — stops between nodes
handle.cancel()
```

### Resume after crash

```python
from pocoflow import WorkflowDB, Flow

db = WorkflowDB("pocoflow.db")

# Find the failed run
runs = [r for r in db.list_runs() if r["status"] == "failed"]
failed = runs[0]

# Restore store from the last successful checkpoint
checkpoints = db.get_checkpoints(failed["run_id"])
last = checkpoints[-1]
store = db.load_checkpoint(failed["run_id"], step=last["step"])

# Resume from the node after the last checkpoint
flow = Flow(start=my_flow_start, db_path="pocoflow.db")
flow.run(store, resume_from=node_after_crash)
```

---

## Streamlit Monitor UI

Visualise and manage all workflow runs from a browser.

**Standalone:**
```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

**Embedded in any Streamlit page:**
```python
from pocoflow.ui.monitor import render_workflow_monitor

render_workflow_monitor("pocoflow.db")
```

Features:
- **Runs table** — run ID, flow name, status badge (✅ 🔄 ❌), started time, duration, step count
- **Auto-refresh** — toggle on with 5 / 10 / 30 s intervals; updates live while flows run
- **Timeline tab** — ordered event log per run: node names, actions, per-node latency (ms), errors
- **Store Inspector tab** — step slider to view the Store state at any checkpoint as a key/value table + raw JSON
- **Resume tab** — generates a ready-to-paste Python code snippet for resuming from the selected checkpoint

---

## Logging

PocoFlow uses [dd-logging](https://github.com/digital-duck/dd-logging) for structured,
namespaced, file-backed log output.

```python
from pocoflow.logging import setup_logging, get_logger

# Set up once at app start (e.g. in CLI entry point or Streamlit cache_resource)
log_path = setup_logging("run", log_level="debug", adapter="openrouter")
# → logs/run-openrouter-20260217-143022.log

# In any module
_log = get_logger("nodes.summarise")   # → pocoflow.nodes.summarise
_log.info("summarising  len=%d", len(text))
```

Logger hierarchy:
```
pocoflow
├── pocoflow.store
├── pocoflow.node
├── pocoflow.flow
├── pocoflow.db
└── pocoflow.runner
```

---

## Migrating from PocketFlow

```python
# Before
from pocketflow import Node, Flow

node_a >> node_b                 # creates "default" edge — causes UserWarning
node_a - "action" >> node_b      # named edge (correct but inconsistent)
shared = {}                      # raw dict — no type safety

# After
from pocoflow import Node, Flow, Store

node_a.then("action", node_b)    # single unambiguous API, always
shared = Store(data=shared_dict) # typed, observable, checkpointable
flow.run(shared)                 # plain dict also accepted for backward compat
```

---

## Project Layout

```
pocoflow/
  __init__.py      — public API: Store, Node, AsyncNode, Flow, WorkflowDB, RunHandle
  store.py         — typed, observable, JSON-checkpointable shared state
  node.py          — Node (sync) + AsyncNode (async) + retry
  flow.py          — directed graph runner: hooks, JSON + SQLite checkpoints, background
  db.py            — WorkflowDB: SQLite schema, CRUD for runs / checkpoints / events
  logging.py       — dd-logging wrapper (pocoflow.* namespace)
  runner.py        — RunHandle: status, wait, cancel
  ui/
    monitor.py     — Streamlit workflow monitor (standalone + embeddable)
examples/
  hello.py         — minimal two-node flow with hooks
tests/
  test_pocoflow.py — 25 tests: Store, Node, Flow, WorkflowDB, RunHandle
docs/
  design.md        — architecture, design decisions, migration guide
```

---

## Comparison with PocketFlow

| Feature | PocketFlow | PocoFlow v0.2 |
|---------|-----------|--------------|
| Core size | ~100 lines | ~600 lines |
| Shared state | raw dict | typed `Store` with schema |
| Edge API | `>>` and `- "action" >>` (confusing) | `.then("action", node)` only |
| Async nodes | manual `asyncio.run()` per node | `AsyncNode.exec_async()` |
| Observability | none | 4-event hook system |
| Checkpointing | none | JSON + SQLite (`WorkflowDB`) |
| Event log | none | `pf_events` table — full audit trail |
| Long-running | none | `run_background()` → `RunHandle` |
| Retry | none | `max_retries` + `retry_delay` on any Node |
| Wildcard edges | none | `.then("*", fallback)` |
| Logging | manual | dd-logging (`pocoflow.*` namespace) |
| Monitor UI | none | Streamlit monitor with auto-refresh |
| External deps | 0 | pocketflow + dd-logging (both stdlib-only) |

---

## Relationship to PocketFlow

PocoFlow is spiritually a child of PocketFlow. We kept:
- The `prep | exec | post` nano-ETL abstraction — beautiful and correct
- Zero vendor lock-in — bring your own LLM client
- No framework magic — every behaviour is traceable to code you can read in minutes

We added what production LLM workflows actually demand:
- Typed, observable, checkpointable `Store`
- Unambiguous `.then()` edge API (no more `UserWarning`)
- `AsyncNode` with `exec_async()`
- Hook system for pluggable observability
- SQLite backend — full audit log, queryable checkpoints, crash recovery
- `run_background()` for long-running agentic workflows
- Streamlit monitor — see every run, every node, every store state
- dd-logging — structured, file-backed, namespaced logs out of the box

**PocketFlow** stays listed as a dependency — as a nod to its inspiration and to ease
migration for projects already using it.

---

## License

MIT — see [LICENSE](LICENSE).
Copyright © 2026 digital-duck.
