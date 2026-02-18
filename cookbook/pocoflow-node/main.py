"""PocoFlow Node — single-node summarisation with retry.

Demonstrates: prep/exec/post lifecycle, max_retries, Store.
"""

import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class SummarizeNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["data"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        text, llm, model = prep_result
        if not text:
            return "Empty text"
        prompt = f"Summarize this text in 10 words: {text}"
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["summary"] = exec_result
        return "done"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Summarize a text about PocoFlow using an LLM."""
    text = """\
    PocoFlow is a lightweight LLM workflow orchestration framework.
    It models every node as a nano-ETL unit with prep, exec, and post phases.
    Nodes connect via named action edges for unambiguous routing.
    It supports retry, async execution, SQLite checkpointing, and Streamlit monitoring.
    """

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])
    store = Store(
        data={"data": text, "summary": "", "_llm": llm, "_model": model},
        name="summarize_demo",
    )

    flow = Flow(start=SummarizeNode())
    flow.run(store)

    print(f"\nInput:   {text.strip()}")
    print(f"\nSummary: {store['summary']}")


if __name__ == "__main__":
    main()
