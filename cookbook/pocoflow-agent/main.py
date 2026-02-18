"""PocoFlow Agent — research agent with web search.

Demonstrates: multi-node agent loop, YAML structured output, DuckDuckGo search.
"""

import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import DecideAction, SearchWeb, AnswerQuestion


@click.command()
@click.argument("question", default="Who won the Nobel Prize in Physics 2024?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(question, provider, model):
    """Research a question using web search and LLM reasoning."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    decide = DecideAction()
    search = SearchWeb()
    answer = AnswerQuestion()

    decide.then("search", search)
    decide.then("answer", answer)
    search.then("decide", decide)

    store = Store(
        data={
            "question": question,
            "context": "",
            "answer": "",
            "_llm": llm,
            "_model": model,
        },
        name="research_agent",
    )

    print(f"Processing question: {question}")
    flow = Flow(start=decide)
    flow.run(store)
    print(f"\nFinal Answer:\n{store['answer']}")


if __name__ == "__main__":
    main()
