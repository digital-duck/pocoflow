"""PocoFlow Supervisor — supervised research agent.

Demonstrates: supervisor pattern, answer validation, retry loop.
Original PocketFlow uses Flow-as-Node; here we flatten to a single flow.
"""

import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import DecideAction, SearchWeb, UnreliableAnswerNode, SupervisorNode


@click.command()
@click.argument("question", default="Who won the Nobel Prize in Physics 2024?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(question, provider, model):
    """Research a question with supervisor validation."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    decide = DecideAction()
    search = SearchWeb()
    answer = UnreliableAnswerNode()
    supervisor = SupervisorNode()

    decide.then("search", search)
    decide.then("answer", answer)
    search.then("decide", decide)
    answer.then("check", supervisor)
    supervisor.then("retry", decide)

    store = Store(
        data={
            "question": question,
            "context": "",
            "answer": "",
            "_llm": llm,
            "_model": model,
        },
        name="supervised_agent",
    )

    print(f"Processing question: {question}")
    flow = Flow(start=decide)
    flow.run(store)
    print(f"\nFinal Answer:\n{store['answer']}")


if __name__ == "__main__":
    main()
