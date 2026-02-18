"""PocoFlow Batch — translate a document into multiple languages.

Demonstrates: batch processing pattern with a single Node.
PocoFlow doesn't have a built-in BatchNode, so we loop inside exec().
"""

import os
import time
import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class TranslateNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        text = store["text"]
        languages = store["languages"]
        llm = store["_llm"]
        model = store.get("_model")
        return [(text, lang) for lang in languages], llm, model

    def exec(self, prep_result):
        items, llm, model = prep_result
        results = []
        for text, language in items:
            prompt = f"""\
Please translate the following markdown into {language}.
Keep the original markdown format, links and code blocks.
Return only the translated text, no commentary.

Original:
{text}

Translated:"""
            response = llm.call(prompt, model=model)
            if not response.success:
                raise RuntimeError(f"LLM failed: {response.error_history}")
            print(f"  Translated → {language}")
            results.append({"language": language, "translation": response.content})
        return results

    def post(self, store, prep_result, exec_result):
        output_dir = store["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        for item in exec_result:
            filename = os.path.join(output_dir, f"README_{item['language'].upper()}.md")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(item["translation"])
            print(f"  Saved {filename}")

        return "done"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Translate the PocoFlow README into multiple languages."""
    readme_path = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
    with open(readme_path) as f:
        text = f.read()

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    store = Store(
        data={
            "text": text,
            "languages": ["Chinese", "Spanish", "French"],
            "output_dir": os.path.join(os.path.dirname(__file__), "translations"),
            "_llm": llm,
            "_model": model,
        },
        name="batch_translate",
    )

    print(f"Translating into {len(store['languages'])} languages...")
    t0 = time.perf_counter()

    flow = Flow(start=TranslateNode())
    flow.run(store)

    print(f"\nDone in {time.perf_counter() - t0:.1f}s")
    print(f"Translations saved to: {store['output_dir']}")


if __name__ == "__main__":
    main()
