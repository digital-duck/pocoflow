"""PocoFlow Structured Output — resume parser with YAML extraction.

Demonstrates: LLM structured output, YAML parsing, assertion-based validation,
retry on parse failure.
"""

import yaml
import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class ResumeParserNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return {
            "resume_text": store["resume_text"],
            "target_skills": store["target_skills"],
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        resume_text = prep_result["resume_text"]
        target_skills = prep_result["target_skills"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        skill_list = "\n".join(f"{i}: {s}" for i, s in enumerate(target_skills))

        prompt = f"""\
Analyze the resume below. Output ONLY the requested information in YAML format.

**Resume:**
```
{resume_text}
```

**Target Skills (use these indexes):**
```
{skill_list}
```

**YAML Output Requirements:**
- Extract `name` (string).
- Extract `email` (string).
- Extract `experience` (list of objects with `title` and `company`).
- Extract `skill_indexes` (list of integers found from the Target Skills list).

**Example Format:**
```yaml
name: Jane Doe
email: jane@example.com
experience:
  - title: Manager
    company: Corp A
  - title: Assistant
    company: Corp B
skill_indexes:
  - 0
  - 2
```

Generate the YAML output now:
"""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")

        # Extract YAML block
        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        result = yaml.safe_load(yaml_str)

        # Validate structure
        assert result is not None, "Parsed YAML is None"
        assert "name" in result, "Missing 'name'"
        assert "email" in result, "Missing 'email'"
        assert isinstance(result.get("experience"), list), "'experience' is not a list"
        assert "skill_indexes" in result, "Missing 'skill_indexes'"
        indexes = result.get("skill_indexes")
        if isinstance(indexes, list):
            for idx in indexes:
                assert isinstance(idx, int), f"Skill index '{idx}' is not an integer"

        return result

    def post(self, store, prep_result, exec_result):
        store["structured_data"] = exec_result

        print("\n=== STRUCTURED RESUME DATA ===\n")
        print(yaml.dump(exec_result, sort_keys=False, allow_unicode=True))
        print("==============================\n")
        return "done"


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(provider, model):
    """Parse a resume and extract structured data via LLM."""
    print("=== Resume Parser — Structured Output ===\n")

    target_skills = [
        "Team leadership & management",  # 0
        "CRM software",                  # 1
        "Project management",            # 2
        "Public speaking",               # 3
        "Microsoft Office",              # 4
        "Python",                        # 5
        "Data Analysis",                 # 6
    ]

    import os
    with open(os.path.join(os.path.dirname(__file__), "data.txt")) as f:
        resume_text = f.read()

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    store = Store(
        data={
            "resume_text": resume_text,
            "target_skills": target_skills,
            "structured_data": {},
            "_llm": llm,
            "_model": model,
        },
        name="resume_parser",
    )

    flow = Flow(start=ResumeParserNode())
    flow.run(store)

    # Show matched skills
    data = store["structured_data"]
    if "skill_indexes" in data and data["skill_indexes"]:
        print("--- Found Target Skills ---")
        for idx in data["skill_indexes"]:
            if 0 <= idx < len(target_skills):
                print(f"  - {target_skills[idx]} (index {idx})")
        print("---------------------------\n")


if __name__ == "__main__":
    main()
