"""PocoFlow Chat with Memory — sliding window + vector retrieval.

Demonstrates: 4-node flow, embeddings, FAISS vector search, conversation archival.
"""

import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import GetUserQuestionNode, RetrieveNode, AnswerNode, EmbedNode


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Chat with sliding-window memory and vector retrieval."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    question = GetUserQuestionNode()
    retrieve = RetrieveNode()
    answer = AnswerNode()
    embed = EmbedNode()

    question.then("retrieve", retrieve)
    retrieve.then("answer", answer)
    answer.then("question", question)
    answer.then("embed", embed)
    embed.then("question", question)

    store = Store(
        data={"messages": [], "_llm": llm, "_model": model},
        name="chat_memory",
    )

    print("=" * 50)
    print("PocoFlow Chat with Memory")
    print("=" * 50)
    print("Keeps 3 most recent conversation pairs.")
    print("Archives older ones and retrieves relevant context.")
    print("Type 'exit' to quit.")
    print("=" * 50)

    flow = Flow(start=question)
    flow.run(store)


if __name__ == "__main__":
    main()
