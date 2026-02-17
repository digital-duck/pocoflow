"""PicoFlow smoke tests — no external dependencies required."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from picoflow import AsyncNode, Flow, Node, Store


# ── Store ─────────────────────────────────────────────────────────────────────

def test_store_basic():
    s = Store({"x": 1})
    assert s["x"] == 1
    s["x"] = 2
    assert s["x"] == 2


def test_store_schema_type_check():
    s = Store({"x": 1}, schema={"x": int})
    with pytest.raises(TypeError):
        s["x"] = "bad"


def test_store_validate_missing_key():
    s = Store({}, schema={"required_key": str})
    with pytest.raises(ValueError, match="required_key"):
        s.validate()


def test_store_observer():
    log = []
    s = Store({"x": 0})
    s.add_observer(lambda k, old, new: log.append((k, old, new)))
    s["x"] = 99
    assert log == [("x", 0, 99)]


def test_store_snapshot_restore(tmp_path):
    s = Store({"a": 1, "b": "hello"}, name="snap_test")
    p = tmp_path / "checkpoint.json"
    s.snapshot(p)
    s2 = Store.restore(p)
    assert s2["a"] == 1
    assert s2["b"] == "hello"
    assert s2._name == "snap_test"


def test_store_contains_and_get():
    s = Store({"x": 42})
    assert "x" in s
    assert "y" not in s
    assert s.get("y", "default") == "default"


# ── Node & Flow ───────────────────────────────────────────────────────────────

class _AddNode(Node):
    def prep(self, store):
        return store["value"]

    def exec(self, v):
        return v + 10

    def post(self, store, prep, result):
        store["value"] = result
        return "next"


def test_single_node_flow():
    store = Store({"value": 5})
    Flow(start=_AddNode()).run(store)
    assert store["value"] == 15


def test_chained_nodes():
    a, b = _AddNode(), _AddNode()
    a.then("next", b)
    store = Store({"value": 0})
    Flow(start=a).run(store)
    assert store["value"] == 20   # +10 twice


def test_wildcard_edge():
    class RouterNode(Node):
        def exec(self, prep): return "unknown_action"
        def post(self, store, prep, result):
            store["routed"] = True
            return result

    class FallbackNode(Node):
        def exec(self, prep): return None
        def post(self, store, prep, result):
            store["fell_back"] = True
            return "done"

    r, f = RouterNode(), FallbackNode()
    r.then("*", f)
    store = Store({"routed": False, "fell_back": False})
    Flow(start=r).run(store)
    assert store["fell_back"] is True


def test_flow_hooks():
    starts, ends = [], []

    flow = Flow(start=_AddNode())
    flow.on("node_start", lambda name, s: starts.append(name))
    flow.on("node_end", lambda name, action, elapsed, s: ends.append((name, action)))

    store = Store({"value": 0})
    flow.run(store)
    assert starts == ["_AddNode"]
    assert ends == [("_AddNode", "next")]


def test_flow_max_steps():
    class LoopNode(Node):
        def exec(self, prep): return None
        def post(self, store, prep, result): return "loop"

    n = LoopNode()
    n.then("loop", n)   # infinite loop
    with pytest.raises(RuntimeError, match="max_steps"):
        Flow(start=n, max_steps=5).run(Store({}))


def test_flow_checkpoint(tmp_path):
    store = Store({"value": 0})
    flow = Flow(start=_AddNode(), checkpoint_dir=tmp_path)
    flow.run(store)
    files = list(tmp_path.glob("step_*_*.json"))
    assert len(files) == 1
    restored = Store.restore(files[0])
    assert restored["value"] == 10


# ── Retry ─────────────────────────────────────────────────────────────────────

def test_retry_succeeds_on_third_attempt():
    attempts = [0]

    class FlakyNode(Node):
        max_retries = 3
        retry_delay = 0.0

        def exec(self, prep):
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("not yet")
            return "ok"

        def post(self, store, prep, result):
            store["result"] = result
            return "done"

    store = Store({"result": ""})
    Flow(start=FlakyNode()).run(store)
    assert attempts[0] == 3
    assert store["result"] == "ok"


def test_retry_exhausted_raises():
    class AlwaysFailNode(Node):
        max_retries = 2
        retry_delay = 0.0
        def exec(self, prep): raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        Flow(start=AlwaysFailNode()).run(Store({}))


# ── AsyncNode ─────────────────────────────────────────────────────────────────

class _AsyncDouble(AsyncNode):
    def prep(self, store):
        return store["value"]

    async def exec_async(self, v):
        await asyncio.sleep(0)
        return v * 2

    def post(self, store, prep, result):
        store["value"] = result
        return "done"


def test_async_node():
    store = Store({"value": 7})
    Flow(start=_AsyncDouble()).run(store)
    assert store["value"] == 14


def test_async_gather():
    class GatherNode(AsyncNode):
        def prep(self, store): return [1, 2, 3]

        async def exec_async(self, items):
            async def double(x):
                await asyncio.sleep(0)
                return x * 2
            return await asyncio.gather(*[double(i) for i in items])

        def post(self, store, prep, result):
            store["results"] = result
            return "done"

    store = Store({"results": []})
    Flow(start=GatherNode()).run(store)
    assert store["results"] == [2, 4, 6]


# ── WorkflowDB ────────────────────────────────────────────────────────────────

from picoflow.db import WorkflowDB


def test_db_create_and_list_runs(tmp_path):
    db = WorkflowDB(tmp_path / "test.db")
    db.create_run("r1", "my_flow")
    runs = db.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "r1"
    assert runs[0]["flow_name"] == "my_flow"
    assert runs[0]["status"] == "running"


def test_db_update_run(tmp_path):
    db = WorkflowDB(tmp_path / "test.db")
    db.create_run("r1")
    db.update_run("r1", status="completed", total_steps=3)
    run = db.get_run("r1")
    assert run["status"] == "completed"
    assert run["total_steps"] == 3


def test_db_save_and_load_checkpoint(tmp_path):
    db = WorkflowDB(tmp_path / "test.db")
    db.create_run("r1")
    store = Store({"x": 42, "msg": "hello"})
    db.save_checkpoint("r1", step=0, node_name="MyNode", store=store)
    checkpoints = db.get_checkpoints("r1")
    assert len(checkpoints) == 1
    restored = db.load_checkpoint("r1", step=0)
    assert restored["x"] == 42
    assert restored["msg"] == "hello"


def test_db_load_checkpoint_missing(tmp_path):
    db = WorkflowDB(tmp_path / "test.db")
    db.create_run("r1")
    with pytest.raises(KeyError):
        db.load_checkpoint("r1", step=99)


def test_db_events(tmp_path):
    db = WorkflowDB(tmp_path / "test.db")
    db.create_run("r1")
    db.save_event("r1", "flow_start", node_name="A")
    db.save_event("r1", "node_end", step=0, node_name="A", action="done", elapsed_ms=42.0)
    db.save_event("r1", "flow_end", step=1)
    events = db.get_events("r1")
    assert len(events) == 3
    assert events[0]["event"] == "flow_start"
    assert events[1]["elapsed_ms"] == 42.0
    assert events[2]["event"] == "flow_end"


def test_flow_with_db(tmp_path):
    db_path = tmp_path / "flow.db"
    store = Store({"value": 5})
    flow = Flow(start=_AddNode(), db_path=db_path, flow_name="test_flow")
    flow.run(store)

    db = WorkflowDB(db_path)
    runs = db.list_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["flow_name"] == "test_flow"
    assert runs[0]["total_steps"] == 1

    # Checkpoint was saved
    ckpts = db.get_checkpoints(runs[0]["run_id"])
    assert len(ckpts) == 1
    restored = db.load_checkpoint(runs[0]["run_id"], step=0)
    assert restored["value"] == 15

    # Events were recorded
    events = db.get_events(runs[0]["run_id"])
    event_names = [e["event"] for e in events]
    assert "flow_start" in event_names
    assert "node_end" in event_names
    assert "flow_end" in event_names


# ── Background runner ─────────────────────────────────────────────────────────

import time as _time
from picoflow.runner import RunHandle


class _SlowNode(Node):
    def exec(self, prep):
        _time.sleep(0.1)
        return "done"

    def post(self, store, prep, result):
        store["done"] = True
        return "done"


def test_background_runner_completes(tmp_path):
    flow = Flow(start=_SlowNode(), db_path=tmp_path / "bg.db", flow_name="bg_test")
    handle = flow.run_background(Store({"done": False}))

    assert isinstance(handle, RunHandle)
    result = handle.wait(timeout=5)
    assert result["done"] is True
    assert handle.status == "completed"


def test_background_runner_timeout(tmp_path):
    class _VerySlowNode(Node):
        def exec(self, prep): _time.sleep(10); return "done"

    flow = Flow(start=_VerySlowNode())
    handle = flow.run_background(Store({}))
    with pytest.raises(TimeoutError):
        handle.wait(timeout=0.05)


def test_background_runner_without_db():
    """RunHandle.status works even without a database."""
    flow = Flow(start=_SlowNode())
    handle = flow.run_background(Store({"done": False}))
    result = handle.wait(timeout=5)
    assert result["done"] is True
    assert handle.status in ("completed", "running")  # may be completed by now
