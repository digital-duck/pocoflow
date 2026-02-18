"""PocoFlow CLI HITL — human-in-the-loop joke generator."""

import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class GetTopicNode(Node):
    def exec(self, prep_result):
        return input("What topic would you like a joke about? ")

    def post(self, store, prep_result, exec_result):
        store["topic"] = exec_result
        return "generate"


class GenerateJokeNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        topic = store.get("topic", "anything")
        disliked = store.get("disliked_jokes", [])
        llm = store["_llm"]
        model = store.get("_model")

        if disliked:
            disliked_str = "; ".join(disliked)
            prompt = (
                f"The user did not like these jokes: [{disliked_str}]. "
                f"Please generate a new, different one-liner joke about {topic}."
            )
        else:
            prompt = f"Please generate a one-liner joke about: {topic}. Make it short and funny."
        return prompt, llm, model

    def exec(self, prep_result):
        prompt, llm, model = prep_result
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["current_joke"] = exec_result
        print(f"\nJoke: {exec_result}")
        return "feedback"


class GetFeedbackNode(Node):
    def exec(self, prep_result):
        while True:
            feedback = input("Did you like this joke? (yes/no): ").strip().lower()
            if feedback in ("yes", "y", "no", "n"):
                return feedback
            print("Invalid input. Please type 'yes' or 'no'.")

    def post(self, store, prep_result, exec_result):
        if exec_result in ("yes", "y"):
            print("Great! Glad you liked it.")
            return "done"

        store.setdefault("disliked_jokes", []).append(store.get("current_joke", ""))
        print("Okay, let me try another one.")
        return "retry"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Interactive joke generator with human-in-the-loop feedback."""
    print("Welcome to the PocoFlow Joke Generator!\n")

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    get_topic = GetTopicNode()
    generate = GenerateJokeNode()
    feedback = GetFeedbackNode()

    get_topic.then("generate", generate)
    generate.then("feedback", feedback)
    feedback.then("retry", generate)

    store = Store(
        data={"_llm": llm, "_model": model},
        name="cli_hitl",
    )

    flow = Flow(start=get_topic)
    flow.run(store)

    print("\nThanks for using the Joke Generator!")


if __name__ == "__main__":
    main()
