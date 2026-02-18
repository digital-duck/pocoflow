"""PocoFlow Workflow — article writing pipeline.

Demonstrates: multi-step workflow, YAML structured output, batch-in-exec pattern.
Original PocketFlow uses BatchNode; here we loop inside exec().
"""

import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import GenerateOutline, WriteSections, ApplyStyle


@click.command()
@click.argument("topic", default="AI Safety")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(topic, provider, model):
    """Write an article on a given topic using a 3-step LLM pipeline."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    outline = GenerateOutline()
    write = WriteSections()
    style = ApplyStyle()

    outline.then("default", write)
    write.then("default", style)

    store = Store(
        data={
            "topic": topic,
            "sections": [],
            "draft": "",
            "final_article": "",
            "_llm": llm,
            "_model": model,
        },
        name="article_workflow",
    )

    print(f"\n=== Starting Article Workflow on Topic: {topic} ===\n")
    flow = Flow(start=outline)
    flow.run(store)

    print("\n=== Workflow Completed ===\n")
    print(f"Topic: {store['topic']}")
    print(f"Draft Length: {len(store['draft'])} characters")
    print(f"Final Article Length: {len(store['final_article'])} characters")


if __name__ == "__main__":
    main()
