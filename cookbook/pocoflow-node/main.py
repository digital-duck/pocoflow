"""PocoFlow Node — single-node summarisation with retry.

Demonstrates: prep/exec/post lifecycle, max_retries, Store.
"""

from pocoflow import Node, Flow, Store
from utils import call_llm


class SummarizeNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["data"]

    def exec(self, prep_result):
        if not prep_result:
            return "Empty text"
        prompt = f"Summarize this text in 10 words: {prep_result}"
        return call_llm(prompt)

    def post(self, store, prep_result, exec_result):
        store["summary"] = exec_result
        return "done"


if __name__ == "__main__":
    text = """\
    PocoFlow is a lightweight LLM workflow orchestration framework.
    It models every node as a nano-ETL unit with prep, exec, and post phases.
    Nodes connect via named action edges for unambiguous routing.
    It supports retry, async execution, SQLite checkpointing, and Streamlit monitoring.
    """

    store = Store(data={"data": text, "summary": ""}, name="summarize_demo")
    flow = Flow(start=SummarizeNode())
    flow.run(store)

    print(f"\nInput:   {text.strip()}")
    print(f"\nSummary: {store['summary']}")
