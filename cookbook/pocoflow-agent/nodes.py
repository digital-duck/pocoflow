"""Agent nodes: decide, search, answer."""

import re
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
Decide the next action based on the context and available actions.
Return your response in this format:

```yaml
thinking: |
    <your step-by-step reasoning process>
action: search OR answer
reason: |
    <why you chose this action>
answer: |
    <if action is answer, leave empty if searching>
search_query: <specific search query if action is search>
```
IMPORTANT: Use the | block scalar for thinking, reason and answer fields.
Keep search_query as a single line string.
"""
        response = call_llm(prompt)

        # Extract YAML block
        match = re.search(r"```yaml(.*?)```", response, re.DOTALL | re.IGNORECASE)
        yaml_str = match.group(1).strip() if match else response.strip()
        decision = yaml.safe_load(yaml_str)
        return decision

    def post(self, store, prep_result, exec_result):
        if exec_result["action"] == "search":
            store["search_query"] = exec_result["search_query"]
            print(f"  -> Searching for: {exec_result['search_query']}")
        else:
            store["context"] = exec_result.get("answer", "")
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


class AnswerQuestion(Node):
    def prep(self, store):
        return store["question"], store.get("context") or ""

    def exec(self, prep_result):
        question, context = prep_result
        print("Crafting final answer...")
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
        print("Answer generated successfully")
        return "done"
