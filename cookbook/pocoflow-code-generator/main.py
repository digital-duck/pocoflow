"""PocoFlow Code Generator — test-driven code generation.

Demonstrates: code generation, test execution, revision loop, YAML structured output.
Original PocketFlow uses BatchNode for RunTests; PocoFlow loops inside exec().
"""

import sys
from pocoflow import Flow, Store
from nodes import GenerateTestCases, ImplementFunction, RunTests, Revise


def main():
    requirement = "Write a function called 'merge_sorted' that takes two sorted lists and returns a single sorted list."
    if len(sys.argv) > 1:
        requirement = " ".join(sys.argv[1:])

    gen_tests = GenerateTestCases()
    implement = ImplementFunction()
    run_tests = RunTests()
    revise = Revise()

    gen_tests.then("default", implement)
    implement.then("default", run_tests)
    run_tests.then("success", None)  # no successor -> ends
    run_tests.then("failure", revise)
    revise.then("default", run_tests)

    store = Store(
        data={
            "requirement": requirement,
            "test_cases": [],
            "implementation": "",
            "test_results": [],
            "revision_count": 0,
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
