"""PocoFlow Tool Embeddings — generate text embeddings via OpenAI API.

Demonstrates: tool integration, OpenAI embeddings API, single-node flow.
"""

import os
import click
from openai import OpenAI
from pocoflow import Node, Flow, Store


class EmbeddingNode(Node):
    def prep(self, store):
        return store["text"], store["_client"]

    def exec(self, prep_result):
        text, client = prep_result
        print(f"Generating embedding for: {text[:60]}...")
        response = client.embeddings.create(model="text-embedding-ada-002", input=text)
        return response.data[0].embedding

    def post(self, store, prep_result, exec_result):
        store["embedding"] = exec_result
        print(f"Embedding dimension: {len(exec_result)}")
        print(f"First 5 values: {exec_result[:5]}")
        return "done"


@click.command()
@click.argument("text", default="What is the meaning of life?")
def main(text):
    """Generate a text embedding using OpenAI's embeddings API."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    store = Store(
        data={"text": text, "embedding": [], "_client": client},
        name="embeddings",
    )

    flow = Flow(start=EmbeddingNode())
    flow.run(store)


if __name__ == "__main__":
    main()
