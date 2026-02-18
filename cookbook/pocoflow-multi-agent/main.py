"""PocoFlow Multi-Agent — Taboo word-guessing game with two LLM agents."""

import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class HintNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return (
            store["target_word"],
            store["forbidden_words"],
            store.get("past_guesses", []),
            store["_llm"],
            store.get("_model"),
        )

    def exec(self, prep_result):
        target, forbidden, past_guesses, llm, model = prep_result
        prompt = f"Generate a hint for '{target}'\nForbidden words: {forbidden}"
        if past_guesses:
            prompt += f"\nPrevious wrong guesses: {past_guesses}\nMake hint more specific."
        prompt += "\nUse at most 5 words. Reply with ONLY the hint."

        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content.strip()

    def post(self, store, prep_result, exec_result):
        store["current_hint"] = exec_result
        print(f"  Hinter: {exec_result}")
        return "guess"


class GuessNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return (
            store["current_hint"],
            store.get("past_guesses", []),
            store["_llm"],
            store.get("_model"),
        )

    def exec(self, prep_result):
        hint, past_guesses, llm, model = prep_result
        prompt = f"Given hint: '{hint}', past wrong guesses: {past_guesses}, make a new guess. Reply with a SINGLE word:"
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        guess = response.content.strip().split()[0] if response.content else ""
        return guess

    def post(self, store, prep_result, exec_result):
        guess = exec_result.strip().lower()
        target = store["target_word"].lower()
        print(f"  Guesser: {exec_result}")

        if guess == target:
            print("\n  Correct! Game Over!")
            store["won"] = True
            return "end"

        store.setdefault("past_guesses", []).append(exec_result)
        rounds = store.get("round", 0) + 1
        store["round"] = rounds

        if rounds >= store.get("max_rounds", 10):
            print(f"\n  Max rounds reached. The word was '{store['target_word']}'.")
            store["won"] = False
            return "end"

        return "hint"


class EndNode(Node):
    def exec(self, prep_result):
        return "done"


@click.command()
@click.option("--target", default="nostalgic", help="Target word to guess")
@click.option("--forbidden", default="memory,past,remember,feeling,longing", help="Comma-separated forbidden words")
@click.option("--rounds", default=10, help="Maximum rounds")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(target, forbidden, rounds, provider, model):
    """Two LLM agents play Taboo: one gives hints, the other guesses."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])
    forbidden_list = [w.strip() for w in forbidden.split(",")]

    print("=========== Taboo Game Starting! ===========")
    print(f"Target word: {target}")
    print(f"Forbidden words: {forbidden_list}")
    print(f"Max rounds: {rounds}")
    print("============================================")

    hint = HintNode()
    guess = GuessNode()
    end = EndNode()

    hint.then("guess", guess)
    guess.then("hint", hint)
    guess.then("end", end)

    store = Store(
        data={
            "target_word": target,
            "forbidden_words": forbidden_list,
            "max_rounds": rounds,
            "past_guesses": [],
            "round": 0,
            "_llm": llm,
            "_model": model,
        },
        name="multi_agent",
    )

    flow = Flow(start=hint)
    flow.run(store)

    print("=========== Game Complete! ===========")


if __name__ == "__main__":
    main()
