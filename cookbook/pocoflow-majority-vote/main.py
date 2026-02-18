"""PocoFlow Majority Vote — consensus via repeated LLM sampling."""

import collections
import click
import yaml
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class MajorityVoteNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return (
            store["question"],
            store["num_tries"],
            store["_llm"],
            store.get("_model"),
        )

    def exec(self, prep_result):
        question, num_tries, llm, model = prep_result
        results = []
        for i in range(num_tries):
            prompt = f"""You are a helpful assistant. Please answer the user's question below.
Question: {question}

Return strictly using the following YAML structure:
```yaml
thinking: |
    (Your thinking process here)
answer: 0.123 # Final answer as a decimal with 3 decimal places
```"""
            try:
                response = llm.call(prompt, model=model)
                if not response.success:
                    print(f"  Attempt {i+1}: LLM call failed, skipping")
                    continue
                raw = response.content
                yaml_part = raw.split("```yaml")[1].split("```")[0].strip()
                parsed = yaml.safe_load(yaml_part)
                if isinstance(parsed, dict) and "answer" in parsed:
                    results.append(str(parsed["answer"]))
                    print(f"  Attempt {i+1}: {parsed['answer']}")
                else:
                    print(f"  Attempt {i+1}: Missing 'answer' in YAML, skipping")
            except Exception as e:
                print(f"  Attempt {i+1}: Error ({e}), skipping")
        return results

    def post(self, store, prep_result, exec_result):
        if not exec_result:
            print("No valid answers obtained.")
            store["majority_answer"] = None
            return "done"

        counter = collections.Counter(exec_result)
        best_answer, freq = counter.most_common(1)[0]
        store["majority_answer"] = best_answer

        print("========================")
        print("All structured answers:", exec_result)
        print("Majority vote =>", best_answer)
        print("Frequency =>", freq)
        print("========================")
        return "done"


DEFAULT_PROBLEM = (
    "You work at a shoe factory. In front of you, there are three pairs of "
    "shoes (six individual shoes) with the following sizes: two size 4s, two "
    "size 5s, and two size 6s. The factory defines an 'acceptable pair' as "
    "two shoes that differ in size by a maximum of one size (e.g., a size 5 "
    "and a size 6 would be an acceptable pair). If you close your eyes and "
    "randomly pick three pairs of shoes without replacement, what is the "
    "probability that you end up drawing three acceptable pairs?"
)


@click.command()
@click.argument("problem", default=DEFAULT_PROBLEM)
@click.option("--tries", default=5, help="Number of LLM attempts for majority vote")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(problem, tries, provider, model):
    """Run majority-vote reasoning on a problem."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    node = MajorityVoteNode()
    store = Store(
        data={
            "question": problem,
            "num_tries": tries,
            "_llm": llm,
            "_model": model,
        },
        name="majority_vote",
    )
    flow = Flow(start=node)
    flow.run(store)

    print(f"\n=== Final Answer ===")
    print(store["majority_answer"])
    print("====================")


if __name__ == "__main__":
    main()
