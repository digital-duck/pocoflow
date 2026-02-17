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
