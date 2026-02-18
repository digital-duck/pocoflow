"""PocoFlow Tracing — workflow observability with Langfuse.

Demonstrates: decorator-based tracing, Langfuse integration, span creation.
"""

import os
import time
import click
from pocoflow import Node, Flow, Store

try:
    from langfuse import Langfuse
    HAS_LANGFUSE = True
except ImportError:
    HAS_LANGFUSE = False


class TracingContext:
    """Simple tracing context that wraps Langfuse."""

    def __init__(self):
        if not HAS_LANGFUSE:
            print("Warning: langfuse not installed. Tracing disabled.")
            self.client = None
            return
        self.client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

    def create_trace(self, name):
        if not self.client:
            return None
        return self.client.trace(name=name)

    def create_span(self, trace, name, input_data=None):
        if not trace:
            return None
        return trace.span(name=name, input=input_data)

    def end_span(self, span, output_data=None):
        if span:
            span.end(output=output_data)

    def flush(self):
        if self.client:
            self.client.flush()


class TracedNode(Node):
    """Base node class that automatically traces prep/exec/post."""

    def _run(self, store):
        tracer = store.get("_tracer")
        trace = store.get("_trace")
        node_name = type(self).__name__

        if tracer and trace:
            span = tracer.create_span(trace, node_name)
        else:
            span = None

        start = time.time()
        result = super()._run(store)
        duration = time.time() - start

        if span:
            tracer.end_span(span, {"duration_ms": round(duration * 1000), "result": str(result)})

        print(f"  [{node_name}] completed in {duration * 1000:.1f}ms")
        return result


# Example nodes
class GreetingNode(TracedNode):
    def prep(self, store):
        return store.get("name", "World")

    def exec(self, prep_result):
        return f"Hello, {prep_result}!"

    def post(self, store, prep_result, exec_result):
        store["greeting"] = exec_result
        return "default"


class UppercaseNode(TracedNode):
    def prep(self, store):
        return store.get("greeting", "")

    def exec(self, prep_result):
        return prep_result.upper()

    def post(self, store, prep_result, exec_result):
        store["result"] = exec_result
        return "done"


@click.command()
@click.option("--name", default="PocoFlow User", help="Name to greet")
def main(name):
    """Run a traced PocoFlow workflow."""
    tracer = TracingContext()
    trace = tracer.create_trace("greeting_flow")

    greeting = GreetingNode()
    uppercase = UppercaseNode()
    greeting.then("default", uppercase)

    store = Store(
        data={"name": name, "_tracer": tracer, "_trace": trace},
        name="tracing_demo",
    )

    print("=== PocoFlow Tracing Demo ===\n")
    flow = Flow(start=greeting)
    flow.run(store)

    print(f"\nResult: {store.get('result')}")

    tracer.flush()
    if HAS_LANGFUSE:
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        print(f"\nCheck your Langfuse dashboard: {host}")
    else:
        print("\nInstall langfuse for full tracing support.")


if __name__ == "__main__":
    main()
