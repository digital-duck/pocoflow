# PicoFlow

> Lightweight LLM workflow orchestration.
> A hardened evolution of [PocketFlow](https://github.com/The-Pocket/PocketFlow).

Built with love by **Claude & digital-duck** 🦆

---

## What It Is

PicoFlow is a minimal, zero-extra-dependency framework for building LLM pipelines
as **directed graphs of nano-ETL nodes** communicating through a shared, typed Store.

It keeps PocketFlow's best idea — the `prep | exec | post` abstraction — and fixes
four weaknesses that surface in production:

| Weakness | PicoFlow fix |
|----------|-------------|
| Raw dict store — no type safety | `Store` with optional schema + `TypeError` on bad writes |
| Ambiguous `>>` edge API | Single clear API: `.then("action", next_node)` |
| No built-in async support | `AsyncNode.exec_async()` — framework handles `asyncio.run()` |
| No observability or checkpointing | Hook system + `checkpoint_dir` with snapshot/restore |

**Size:** ~320 lines of pure Python stdlib.
**Dependencies:** [pocketflow](https://github.com/The-Pocket/PocketFlow) (for migration compat + inspiration).

---

## Quick Start

```bash
pip install picoflow
```

```python
from picoflow import Node, Flow, Store

class GreetNode(Node):
    def prep(self, store):
        return store["name"]

    def exec(self, name):
        return f"Hello, {name}!"

    def post(self, store, prep, greeting):
        store["greeting"] = greeting
        return "done"

store = Store({"name": "world", "greeting": ""})
Flow(start=GreetNode()).run(store)
print(store["greeting"])   # Hello, world!
```

---

## Core Concepts

### Node — nano-ETL

Every node is a three-phase processing unit:

```
prep(store)              → Extract: read what this node needs from the store
exec(prep_result)        → Transform: do the work (pure, no store side-effects)
post(store, prep, exec)  → Load: write results back, return next action string
```

This maps directly to ETL — hence "nano-ETL for every node":

| Phase | ETL step | Purity |
|-------|----------|--------|
| `prep` | Extract | reads store |
| `exec` | Transform | pure function — retryable, testable without a store |
| `post` | Load + Route | writes store, returns action string |

### Store — typed shared state

```python
store = Store(
    data={"query": "", "result": ""},
    schema={"query": str, "result": str},   # type-checked on every write
    name="my_pipeline",
)
store["query"] = "explain quantum entanglement"
store["query"] = 42  # ← raises TypeError immediately

# Observer: fired on every write
store.add_observer(lambda key, old, new: print(f"{key}: {old!r} → {new!r}"))

# Checkpoint / restore
store.snapshot("/tmp/run_42/step_002.json")
store2 = Store.restore("/tmp/run_42/step_002.json")
```

### Flow — directed graph with hooks

```python
# Wire nodes with unambiguous named edges
a.then("ok", b)
a.then("error", c)
a.then("*", fallback)   # wildcard: matches any other action

# Build and run
flow = Flow(start=a, checkpoint_dir="/tmp/run_42", max_steps=50)

# Hooks — attach to any logger, metrics sink, or UI
flow.on("node_start", lambda name, store: print(f"▶ {name}"))
flow.on("node_end",   lambda name, action, elapsed, store:
                          print(f"✓ {name} → {action}  ({elapsed:.2f}s)"))
flow.on("node_error", lambda name, exc, store: ...)
flow.on("flow_end",   lambda steps, store: print(f"Done in {steps} steps"))

store = Store({"query": "..."})
flow.run(store)

# Resume after crash
store = Store.restore("/tmp/run_42/step_002_MyNode.json")
flow.run(store, resume_from=my_node)
```

### AsyncNode — parallel sub-tasks

```python
from picoflow import AsyncNode
import asyncio

class FetchNode(AsyncNode):
    def prep(self, store):
        return store["urls"]

    async def exec_async(self, urls):
        # true parallelism inside a single node
        return await asyncio.gather(*[fetch(u) for u in urls])

    def post(self, store, prep, results):
        store["pages"] = results
        return "done"
```

### Retry

```python
class CallLLMNode(Node):
    max_retries = 3       # retry exec() up to 3 times
    retry_delay = 1.0     # wait 1 s between retries

    def exec(self, prompt):
        return llm.call(prompt)   # retried automatically on exception
```

---

## Migrating from PocketFlow

```python
# Before
from pocketflow import Node, Flow

node_a >> node_b                     # creates "default" edge — causes UserWarning
node_a - "action" >> node_b          # named edge (correct but inconsistent)

# After
from picoflow import Node, Flow, Store

node_a.then("action", node_b)        # single unambiguous API, always

shared = Store(data=shared_dict)     # wrap existing dict in typed Store
flow.run(shared)                     # Store or plain dict both accepted
```

---

## Project Layout

```
picoflow/
  __init__.py   — public API
  store.py      — Store: typed, observable, checkpointable
  node.py       — Node (sync) + AsyncNode (async via asyncio.run)
  flow.py       — Flow: directed graph runner, hooks, checkpointing
examples/
  hello.py      — minimal single-node example
  branching.py  — multi-node flow with named edges
  async_fetch.py — AsyncNode with asyncio.gather
tests/
  test_store.py
  test_node.py
  test_flow.py
```

---

## Relationship to PocketFlow

PicoFlow is spiritually a child of PocketFlow.  We kept:
- The `prep | exec | post` nano-ETL abstraction (beautiful and correct)
- Zero vendor lock-in — bring your own LLM client
- No framework magic — every behaviour is traceable to code you can read

We added what production use demanded:
- Typed, observable, checkpointable `Store`
- Unambiguous `.then()` edge API
- `AsyncNode` with `exec_async()`
- Hook system for observability
- `checkpoint_dir` for crash recovery

**PocketFlow** stays listed as a dependency — both as a nod to its inspiration
and to ease migration for projects already using it.

---

## License

MIT — see [LICENSE](LICENSE).
Copyright © 2026 digital-duck.
