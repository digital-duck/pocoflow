"""PocoFlow Code Generator — test-driven code generation.

Demonstrates: code generation, test execution, revision loop, YAML structured output.
Original PocketFlow uses BatchNode for RunTests; PocoFlow loops inside exec().
"""

import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import GenerateTestCases, ImplementFunction, RunTests, Revise


@click.command()
@click.argument("requirement", default="Write a function called 'merge_sorted' that takes two sorted lists and returns a single sorted list.")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(requirement, provider, model):
    """Generate code from a requirement using test-driven development."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    gen_tests = GenerateTestCases()
    implement = ImplementFunction()
    run_tests = RunTests()
    revise = Revise()

    gen_tests.then("default", implement)
    implement.then("default", run_tests)
    run_tests.then("success", None)
    run_tests.then("failure", revise)
    revise.then("default", run_tests)

    store = Store(
        data={
            "requirement": requirement,
            "test_cases": [],
            "implementation": "",
            "test_results": [],
            "revision_count": 0,
            "_llm": llm,
            "_model": model,
        },
        name="code_generator",
    )

    print(f"\n=== Code Generator ===")
    print(f"Requirement: {requirement}\n")

    flow = Flow(start=gen_tests)
    flow.run(store)

    print(f"\n=== Result ===")
    print(f"Revisions: {store['revision_count']}")
    print(f"\nFinal Implementation:\n{store['implementation']}")


if __name__ == "__main__":
    main()
