"""PocoFlow A2A — agent-to-agent pattern with research agent."""

import click
import yaml
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


def search_web(query):
    """Simulated web search (replace with real search for production)."""
    return f"Search results for '{query}': [Simulated result — in production, use duckduckgo_search or similar]"


class DecideActionNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        question = store["question"]
        context = store.get("context", "No previous search")
        llm = store["_llm"]
        model = store.get("_model")

        prompt = f"""### CONTEXT
You are a research assistant that can search the web.
Question: {question}
Previous Research: {context}

### ACTION SPACE
[1] search — Look up more information
[2] answer — Answer with current knowledge

Decide the next action:

```yaml
thinking: |
    <reasoning>
action: search OR answer
answer: <if action is answer>
search_query: <if action is search>
```"""
        return prompt, llm, model

    def exec(self, prep_result):
        prompt, llm, model = prep_result
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        return yaml.safe_load(yaml_str)

    def post(self, store, prep_result, exec_result):
        if exec_result["action"] == "search":
            store["search_query"] = exec_result.get("search_query", "")
            print(f"  Searching: {store['search_query']}")
            return "search"
        store["context"] = exec_result.get("answer", "")
        print("  Decided to answer.")
        return "answer"


class SearchWebNode(Node):
    def prep(self, store):
        return store["search_query"]

    def exec(self, prep_result):
        return search_web(prep_result)

    def post(self, store, prep_result, exec_result):
        prev = store.get("context", "")
        store["context"] = prev + f"\n\nSEARCH: {store['search_query']}\nRESULTS: {exec_result}"
        print("  Search complete, analyzing...")
        return "decide"


class AnswerNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        question = store["question"]
        context = store.get("context", "")
        llm = store["_llm"]
        model = store.get("_model")

        prompt = f"""Based on the following information, answer the question.
Question: {question}
Research: {context}

Provide a comprehensive answer."""
        return prompt, llm, model

    def exec(self, prep_result):
        prompt, llm, model = prep_result
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["answer"] = exec_result
        print("  Answer generated.")
        return "done"


@click.command()
@click.argument("question", default="Who won the Nobel Prize in Physics 2024?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(question, provider, model):
    """Research agent that searches and answers questions."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    decide = DecideActionNode()
    search = SearchWebNode()
    answer = AnswerNode()

    decide.then("search", search)
    decide.then("answer", answer)
    search.then("decide", decide)

    store = Store(
        data={"question": question, "_llm": llm, "_model": model},
        name="a2a",
    )

    print(f"Processing: {question}")
    flow = Flow(start=decide)
    flow.run(store)

    print(f"\nFinal Answer:\n{store.get('answer', 'No answer')}")


if __name__ == "__main__":
    main()
