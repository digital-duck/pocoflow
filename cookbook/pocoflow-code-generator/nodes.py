"""Code generator nodes: generate tests, implement, run tests, revise."""

import re
import yaml
from pocoflow import Node
from utils import execute_python


def _llm_call(llm, model, prompt):
    """Helper: call LLM and return content or raise on failure."""
    response = llm.call(prompt, model=model)
    if not response.success:
        raise RuntimeError(f"LLM failed: {response.error_history}")
    return response.content


class GenerateTestCases(Node):
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        return store["requirement"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        requirement, llm, model = prep_result
        prompt = f"""Generate test cases for this requirement:

{requirement}

Return test cases in YAML format:

```yaml
test_cases:
  - input: "merge_sorted([1, 3, 5], [2, 4, 6])"
    expected: "[1, 2, 3, 4, 5, 6]"
  - input: "merge_sorted([], [1, 2])"
    expected: "[1, 2]"
```

Generate 5 diverse test cases covering edge cases."""
        response = _llm_call(llm, model, prompt)
        match = re.search(r"```yaml(.*?)```", response, re.DOTALL)
        yaml_str = match.group(1).strip() if match else response.strip()
        return yaml.safe_load(yaml_str)

    def post(self, store, prep_result, exec_result):
        store["test_cases"] = exec_result["test_cases"]
        print(f"Generated {len(exec_result['test_cases'])} test cases:")
        for tc in exec_result["test_cases"]:
            print(f"  {tc['input']} -> {tc['expected']}")
        return "default"


class ImplementFunction(Node):
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        return {
            "requirement": store["requirement"],
            "test_cases": store["test_cases"],
            "previous_impl": store.get("implementation") or "",
            "test_results": store.get("test_results") or [],
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        llm = prep_result["llm"]
        model = prep_result["model"]
        test_info = "\n".join(
            f"  {tc['input']} -> {tc['expected']}"
            for tc in prep_result["test_cases"]
        )
        context = f"""Implement the following requirement:

{prep_result['requirement']}

Test cases:
{test_info}
"""
        if prep_result["previous_impl"]:
            context += f"""
Previous implementation (had failures):
{prep_result['previous_impl']}

Test results:
{prep_result['test_results']}

Fix the issues.
"""

        prompt = context + """
Return ONLY the Python function implementation, no test code.
Wrap in ```python ... ```."""

        response = _llm_call(llm, model, prompt)
        match = re.search(r"```python(.*?)```", response, re.DOTALL)
        return match.group(1).strip() if match else response.strip()

    def post(self, store, prep_result, exec_result):
        store["implementation"] = exec_result
        print(f"\nImplementation:\n{exec_result}\n")
        return "default"


class RunTests(Node):
    """Runs all test cases. Replaces PocketFlow's BatchNode with loop in exec()."""

    def prep(self, store):
        return {
            "implementation": store["implementation"],
            "test_cases": store["test_cases"],
        }

    def exec(self, prep_result):
        results = []
        for tc in prep_result["test_cases"]:
            code = f"""{prep_result['implementation']}

result = {tc['input']}
expected = {tc['expected']}
assert result == expected, f"Got {{result}}, expected {{expected}}"
print("PASS")
"""
            output = execute_python(code)
            passed = "PASS" in output and "Error" not in output and "Traceback" not in output
            results.append({
                "input": tc["input"],
                "expected": tc["expected"],
                "output": output.strip(),
                "passed": passed,
            })
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {tc['input']}")

        return results

    def post(self, store, prep_result, exec_result):
        store["test_results"] = exec_result
        all_passed = all(r["passed"] for r in exec_result)
        passed = sum(1 for r in exec_result if r["passed"])
        total = len(exec_result)
        print(f"\n  Results: {passed}/{total} passed")

        if all_passed:
            print("  All tests passed!")
            return "success"

        if store["revision_count"] >= 3:
            print("  Max revisions reached, stopping.")
            return "success"

        return "failure"


class Revise(Node):
    def prep(self, store):
        return {
            "requirement": store["requirement"],
            "implementation": store["implementation"],
            "test_results": store["test_results"],
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        llm = prep_result["llm"]
        model = prep_result["model"]
        failures = [r for r in prep_result["test_results"] if not r["passed"]]
        failure_info = "\n".join(
            f"  Input: {f['input']}, Expected: {f['expected']}, Got: {f['output']}"
            for f in failures
        )

        prompt = f"""Fix this Python function:

Requirement: {prep_result['requirement']}

Current implementation:
{prep_result['implementation']}

Failed tests:
{failure_info}

Return ONLY the fixed Python function. Wrap in ```python ... ```."""

        response = _llm_call(llm, model, prompt)
        match = re.search(r"```python(.*?)```", response, re.DOTALL)
        return match.group(1).strip() if match else response.strip()

    def post(self, store, prep_result, exec_result):
        store["implementation"] = exec_result
        store["revision_count"] = store.get("revision_count", 0) + 1
        print(f"\nRevision {store['revision_count']}:\n{exec_result}\n")
        return "default"
