"""PocoFlow Chat — simple conversational chatbot."""

import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class ChatNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        if not store["messages"]:
            print("Welcome to PocoFlow Chat!  Type 'exit' to quit.\n")

        user_input = input("You: ")

        if user_input.strip().lower() == "exit":
            return None

        store["messages"].append({"role": "user", "content": user_input})
        return store["messages"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        if prep_result is None:
            return None
        messages, llm, model = prep_result
        response = llm.call(messages=messages, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        if prep_result is None or exec_result is None:
            print("\nGoodbye!")
            return "exit"

        print(f"\nAssistant: {exec_result}\n")
        store["messages"].append({"role": "assistant", "content": exec_result})
        return "continue"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Interactive chatbot with conversation history."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    chat = ChatNode()
    chat.then("continue", chat)

    store = Store(
        data={"messages": [], "_llm": llm, "_model": model},
        name="chat",
    )

    flow = Flow(start=chat)
    flow.run(store)


if __name__ == "__main__":
    main()
