"""Article workflow nodes: outline, write sections, apply style."""

import re
import yaml
from pocoflow import Node
from utils import call_llm


class GenerateOutline(Node):
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        return store["topic"]

    def exec(self, prep_result):
        prompt = f"""
Create a simple outline for an article about {prep_result}.
Include at most 3 main sections (no subsections).

Output the sections in YAML format as shown below:

```yaml
sections:
    - |
        First section
    - |
        Second section
    - |
        Third section
```"""
        response = call_llm(prompt)
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        return yaml.safe_load(yaml_str)

    def post(self, store, prep_result, exec_result):
        sections = exec_result["sections"]
        store["sections"] = sections

        formatted = "\n".join(f"{i+1}. {s.strip()}" for i, s in enumerate(sections))
        store["outline"] = formatted

        print("===== OUTLINE =====\n")
        print(formatted)
        print("\n===================\n")
        return "default"


class WriteSections(Node):
    """Writes content for each section. Replaces PocketFlow's BatchNode with a loop in exec()."""

    def prep(self, store):
        return store["sections"]

    def exec(self, prep_result):
        results = []
        for i, section in enumerate(prep_result):
            prompt = f"""
Write a short paragraph (MAXIMUM 100 WORDS) about this section:

{section}

Requirements:
- Explain the idea in simple, easy-to-understand terms
- Use everyday language, avoiding jargon
- Keep it very concise (no more than 100 words)
- Include one brief example or analogy
"""
            content = call_llm(prompt)
            print(f"  Completed section {i + 1}/{len(prep_result)}: {section.strip()}")
            results.append((section.strip(), content))
        return results

    def post(self, store, prep_result, exec_result):
        all_sections = []
        for section, content in exec_result:
            all_sections.append(f"## {section}\n\n{content}\n")

        draft = "\n".join(all_sections)
        store["draft"] = draft

        print("\n===== SECTION CONTENTS =====\n")
        for section, content in exec_result:
            print(f"--- {section} ---")
            print(content)
            print()
        print("============================\n")
        return "default"


class ApplyStyle(Node):
    def prep(self, store):
        return store["draft"]

    def exec(self, prep_result):
        prompt = f"""
Rewrite the following draft in a conversational, engaging style:

{prep_result}

Make it:
- Conversational and warm in tone
- Include rhetorical questions that engage the reader
- Add analogies and metaphors where appropriate
- Include a strong opening and conclusion
"""
        return call_llm(prompt)

    def post(self, store, prep_result, exec_result):
        store["final_article"] = exec_result
        print("===== FINAL ARTICLE =====\n")
        print(exec_result)
        print("\n=========================\n")
        return "default"
