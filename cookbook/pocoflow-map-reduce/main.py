"""PocoFlow Map-Reduce — resume qualification evaluation.

Demonstrates: map-reduce pattern, batch-in-exec, YAML structured output.
"""

import os
import yaml
import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


def _llm_call(llm, model, prompt):
    response = llm.call(prompt, model=model)
    if not response.success:
        raise RuntimeError(f"LLM failed: {response.error_history}")
    return response.content


class ReadResumesNode(Node):
    """Map phase: read all resumes from data directory."""

    def prep(self, store):
        return None

    def exec(self, prep_result):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        resume_files = {}
        for filename in sorted(os.listdir(data_dir)):
            if filename.endswith(".txt"):
                with open(os.path.join(data_dir, filename), encoding="utf-8") as f:
                    resume_files[filename] = f.read()
        return resume_files

    def post(self, store, prep_result, exec_result):
        store["resumes"] = exec_result
        print(f"Read {len(exec_result)} resumes")
        return "default"


class EvaluateResumesNode(Node):
    """Batch processing: evaluate each resume via LLM (loop in exec)."""
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        return list(store["resumes"].items()), store["_llm"], store.get("_model")

    def exec(self, prep_result):
        items, llm, model = prep_result
        evaluations = {}
        for filename, content in items:
            prompt = f"""
Evaluate the following resume and determine if the candidate qualifies for an advanced technical role.
Criteria for qualification:
- At least a bachelor's degree in a relevant field
- At least 3 years of relevant work experience
- Strong technical skills relevant to the position

Resume:
{content}

Return your evaluation in YAML format:
```yaml
candidate_name: [Name of the candidate]
qualifies: [true/false]
reasons:
  - [First reason for qualification/disqualification]
  - [Second reason, if applicable]
```
"""
            response = _llm_call(llm, model, prompt)
            yaml_content = response.split("```yaml")[1].split("```")[0].strip() if "```yaml" in response else response
            result = yaml.safe_load(yaml_content)
            evaluations[filename] = result
            status = "QUALIFIED" if result.get("qualifies") else "NOT QUALIFIED"
            print(f"  {result.get('candidate_name', 'Unknown')} ({filename}): {status}")
        return evaluations

    def post(self, store, prep_result, exec_result):
        store["evaluations"] = exec_result
        return "default"


class ReduceResultsNode(Node):
    """Reduce: aggregate evaluation results."""

    def prep(self, store):
        return store["evaluations"]

    def exec(self, prep_result):
        qualified_count = 0
        total_count = len(prep_result)
        qualified_names = []

        for filename, evaluation in prep_result.items():
            if evaluation.get("qualifies"):
                qualified_count += 1
                qualified_names.append(evaluation.get("candidate_name", "Unknown"))

        return {
            "total_candidates": total_count,
            "qualified_count": qualified_count,
            "qualified_percentage": round(qualified_count / total_count * 100, 1) if total_count > 0 else 0,
            "qualified_names": qualified_names,
        }

    def post(self, store, prep_result, exec_result):
        store["summary"] = exec_result

        print(f"\n===== Resume Qualification Summary =====")
        print(f"Total candidates evaluated: {exec_result['total_candidates']}")
        print(f"Qualified candidates: {exec_result['qualified_count']} ({exec_result['qualified_percentage']}%)")
        if exec_result["qualified_names"]:
            print("\nQualified candidates:")
            for name in exec_result["qualified_names"]:
                print(f"  - {name}")
        return "done"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Evaluate resumes using map-reduce pattern."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    read = ReadResumesNode()
    evaluate = EvaluateResumesNode()
    reduce_node = ReduceResultsNode()

    read.then("default", evaluate)
    evaluate.then("default", reduce_node)

    store = Store(
        data={"resumes": {}, "evaluations": {}, "summary": {}, "_llm": llm, "_model": model},
        name="resume_map_reduce",
    )

    print("Starting resume qualification processing...\n")
    flow = Flow(start=read)
    flow.run(store)
    print("\nResume processing complete!")


if __name__ == "__main__":
    main()
