"""Supervisor nodes: decide, search, unreliable answer, supervisor."""

import re
import random
import yaml
from pocoflow import Node
from utils import call_llm, search_web


class DecideAction(Node):
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        context = store.get("context") or "No previous search"
        question = store["question"]
        return question, context

    def exec(self, prep_result):
        question, context = prep_result
        print("Agent deciding what to do next...")

        prompt = f"""
### CONTEXT
You are a research assistant that can search the web.
Question: {question}
Previous Research: {context}

### ACTION SPACE
[1] search
  Description: Look up more information on the web
  Parameters:
    - query (str): What to search for

[2] answer
  Description: Answer the question with current knowledge
  Parameters:
    - answer (str): Final answer to the question

## NEXT ACTION
Return your response in this format:

```yaml
thinking: |
    <your step-by-step reasoning process>
action: search OR answer
reason: |
    <why you chose this action>
search_query: <specific search query if action is search>
```
"""
        response = call_llm(prompt)
        match = re.search(r"```yaml(.*?)```", response, re.DOTALL | re.IGNORECASE)
        yaml_str = match.group(1).strip() if match else response.strip()
        return yaml.safe_load(yaml_str)

    def post(self, store, prep_result, exec_result):
        if exec_result["action"] == "search":
            store["search_query"] = exec_result["search_query"]
            print(f"  -> Searching for: {exec_result['search_query']}")
        else:
            print("  -> Decided to answer")
        return exec_result["action"]


class SearchWeb(Node):
    def prep(self, store):
        return store["search_query"]

    def exec(self, prep_result):
        print(f"Searching the web for: {prep_result}")
        return search_web(prep_result)

    def post(self, store, prep_result, exec_result):
        previous = store.get("context") or ""
        store["context"] = previous + "\n\nSEARCH: " + store["search_query"] + "\nRESULTS: " + exec_result
        print("  Found information, analyzing...")
        return "decide"


class UnreliableAnswerNode(Node):
    def prep(self, store):
        return store["question"], store.get("context") or ""

    def exec(self, prep_result):
        question, context = prep_result

        # 50% chance of dummy answer
        if random.random() < 0.5:
            print("  Generating unreliable dummy answer...")
            return ("Sorry, I'm on a coffee break right now. All information I provide "
                    "is completely made up anyway. The answer is 42, or maybe purple "
                    "unicorns. Who knows? Certainly not me!")

        print("  Crafting final answer...")
        prompt = f"""
### CONTEXT
Based on the following information, answer the question.
Question: {question}
Research: {context}

## YOUR ANSWER:
Provide a comprehensive answer using the research results.
"""
        return call_llm(prompt)

    def post(self, store, prep_result, exec_result):
        store["answer"] = exec_result
        print("  Answer generated")
        return "check"


class SupervisorNode(Node):
    def prep(self, store):
        return store["answer"]

    def exec(self, prep_result):
        print("  Supervisor checking answer quality...")
        nonsense_markers = [
            "coffee break", "purple unicorns", "made up", "42", "Who knows?"
        ]
        is_nonsense = any(marker in prep_result for marker in nonsense_markers)

        if is_nonsense:
            return {"valid": False, "reason": "Answer appears nonsensical"}
        return {"valid": True, "reason": "Answer appears legitimate"}

    def post(self, store, prep_result, exec_result):
        if exec_result["valid"]:
            print(f"  Supervisor APPROVED: {exec_result['reason']}")
            return "approved"
        else:
            print(f"  Supervisor REJECTED: {exec_result['reason']}")
            store["answer"] = ""
            context = store.get("context") or ""
            store["context"] = context + "\n\nNOTE: Previous answer was rejected by supervisor."
            return "retry"
