"""PocoFlow LLM Streaming — real-time response streaming with user interrupt.

Demonstrates: streaming LLM output, threading for user interrupt, single-node flow.
"""

import os
import time
import threading
import click
from pocoflow import Node, Flow, Store


def _get_openai_client(provider):
    """Create an OpenAI-compatible client for the given provider."""
    from openai import OpenAI

    if provider == "openai":
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY")), "gpt-4o"
    elif provider == "openrouter":
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        ), "anthropic/claude-sonnet-4-20250514"
    elif provider == "ollama":
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        return OpenAI(base_url=f"{host}/v1", api_key="ollama"), "llama3.2"
    elif provider == "anthropic":
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "unused")), "gpt-4o"
    else:
        raise ValueError(f"Unsupported streaming provider: {provider}")


class StreamNode(Node):
    def prep(self, store):
        prompt = store["prompt"]
        provider = store.get("_provider", "openai")
        model = store.get("_model")

        client, default_model = _get_openai_client(provider)
        model = model or default_model

        # Create streaming response
        chunks = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            stream=True,
        )

        # Create interrupt event and listener thread
        interrupt_event = threading.Event()

        def wait_for_interrupt():
            input("Press ENTER at any time to interrupt streaming...\n")
            interrupt_event.set()

        listener_thread = threading.Thread(target=wait_for_interrupt, daemon=True)
        listener_thread.start()

        return chunks, interrupt_event, listener_thread

    def exec(self, prep_result):
        chunks, interrupt_event, listener_thread = prep_result
        collected = []

        for chunk in chunks:
            if interrupt_event.is_set():
                print("\n[User interrupted streaming]")
                break
            if (
                hasattr(chunk.choices[0].delta, "content")
                and chunk.choices[0].delta.content is not None
            ):
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                collected.append(text)

        print()  # newline after streaming
        return "".join(collected), interrupt_event, listener_thread

    def post(self, store, prep_result, exec_result):
        response_text, interrupt_event, listener_thread = exec_result
        store["response"] = response_text
        # Clean up the listener thread
        interrupt_event.set()
        return "done"


@click.command()
@click.argument("prompt", default="What is the meaning of life?")
@click.option("--provider", default="openai", help="LLM provider (openai, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(prompt, provider, model):
    """Stream an LLM response in real time with interrupt support."""
    store = Store(
        data={"prompt": prompt, "response": "", "_provider": provider, "_model": model},
        name="llm_streaming",
    )

    print(f"Prompt: {prompt}\n")
    flow = Flow(start=StreamNode())
    flow.run(store)


if __name__ == "__main__":
    main()
