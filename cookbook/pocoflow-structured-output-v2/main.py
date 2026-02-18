"""PocoFlow Structured Output v2 — resume parser with YAML extraction."""

import click
import yaml
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class ResumeParserNode(Node):
    max_retries = 3
    retry_delay = 10.0

    def prep(self, store):
        return {
            "resume_text": store["resume_text"],
            "target_skills": store.get("target_skills", []),
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        resume_text = prep_result["resume_text"]
        target_skills = prep_result["target_skills"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        skill_list = "\n".join(
            [f"{i}: {skill}" for i, skill in enumerate(target_skills)]
        )

        prompt = f"""Analyze the resume below. Output ONLY the requested information in YAML format.

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
- Add a YAML comment explaining the source BEFORE `name`, `email`, `experience`, each item in `experience`, and `skill_indexes`.

**Example Format:**
```yaml
# Found name at top
name: Jane Doe
# Found email in contact info
email: jane@example.com
# Experience section analysis
experience:
  # First job listed
  - title: Manager
    company: Corp A
  # Second job listed
  - title: Assistant
    company: Corp B
# Skills identified from the target list
skill_indexes:
  - 0
  - 2
```

Generate the YAML output now:
"""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")

        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        result = yaml.safe_load(yaml_str)

        assert result is not None, "Parsed YAML is None"
        assert "name" in result, "Missing 'name'"
        assert "email" in result, "Missing 'email'"
        assert "experience" in result, "Missing 'experience'"
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
        print("===============================\n")
        return "done"


SAMPLE_RESUME = """John Smith
Email: john.smith@email.com | Phone: (555) 123-4567

EXPERIENCE
Senior Project Manager | TechCorp Inc. | 2020-Present
- Led cross-functional teams of 15+ members
- Managed $2M+ project budgets using Agile methodology
- Proficient in Microsoft Office and project management tools

Marketing Coordinator | StartupXYZ | 2017-2020
- Developed data-driven marketing campaigns
- Used Python for data analysis and reporting
- Delivered quarterly presentations to stakeholders

SKILLS
Team leadership, Project management, Python, Data Analysis, Public speaking, Microsoft Office
"""

TARGET_SKILLS = [
    "Team leadership & management",
    "CRM software",
    "Project management",
    "Public speaking",
    "Microsoft Office",
    "Python",
    "Data Analysis",
]


@click.command()
@click.option("--resume", default=None, type=click.Path(exists=True), help="Path to resume file")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(resume, provider, model):
    """Parse a resume into structured YAML data."""
    if resume:
        with open(resume) as f:
            resume_text = f.read()
    else:
        resume_text = SAMPLE_RESUME

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    node = ResumeParserNode()
    store = Store(
        data={
            "resume_text": resume_text,
            "target_skills": TARGET_SKILLS,
            "_llm": llm,
            "_model": model,
        },
        name="structured_output_v2",
    )
    flow = Flow(start=node)
    flow.run(store)

    if "structured_data" in store and "skill_indexes" in store["structured_data"]:
        print("--- Found Target Skills ---")
        for idx in store["structured_data"]["skill_indexes"] or []:
            if 0 <= idx < len(TARGET_SKILLS):
                print(f"- {TARGET_SKILLS[idx]} (Index: {idx})")
        print("---------------------------")


if __name__ == "__main__":
    main()
