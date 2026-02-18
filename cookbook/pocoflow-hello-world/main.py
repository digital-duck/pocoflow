"""PocoFlow Hello World — minimal single-node LLM flow."""

import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class AnswerNode(Node):
    def prep(self, store):
        return store["question"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        question, llm, model = prep_result
        response = llm.call(f"Answer concisely:\n{question}", model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["answer"] = exec_result
        print(f"\nAnswer: {exec_result}")
        return "done"


@click.command()
@click.argument("question", default="What is the meaning of life?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(question, provider, model):
    """Ask a question and get a concise answer from an LLM."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    store = Store(
        data={"question": question, "answer": "", "_llm": llm, "_model": model},
        name="hello_world",
    )

    print(f"Question: {question}")
    flow = Flow(start=AnswerNode())
    flow.run(store)


if __name__ == "__main__":
    main()
