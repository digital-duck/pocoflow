"""PocoFlow Tool Search — web search with LLM analysis.

Demonstrates: tool integration, YAML structured output, 2-node flow.
"""

import yaml
import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider

try:
    from google_search_results import GoogleSearch
    HAS_SERPAPI = True
except ImportError:
    HAS_SERPAPI = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def search_web(query: str, num_results: int = 5) -> list[dict]:
    """Search using DuckDuckGo (fallback if SerpAPI unavailable)."""
    if HAS_DDGS:
        results = DDGS().text(query, max_results=num_results)
        return [{"title": r["title"], "link": r["href"], "snippet": r["body"]} for r in results]
    raise RuntimeError("No search backend available. Install duckduckgo-search.")


def _llm_call(llm, model, prompt):
    response = llm.call(prompt, model=model)
    if not response.success:
        raise RuntimeError(f"LLM failed: {response.error_history}")
    return response.content


class SearchNode(Node):
    def prep(self, store):
        return store["query"]

    def exec(self, prep_result):
        print(f"Searching for: {prep_result}")
        return search_web(prep_result)

    def post(self, store, prep_result, exec_result):
        store["search_results"] = exec_result
        print(f"  Found {len(exec_result)} results")
        return "default"


class AnalyzeResultsNode(Node):
    max_retries = 3
    retry_delay = 1.0

    def prep(self, store):
        results_text = "\n\n".join(
            f"Title: {r['title']}\nURL: {r['link']}\nSnippet: {r['snippet']}"
            for r in store["search_results"]
        )
        return results_text, store["query"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        results_text, query, llm, model = prep_result
        print("Analyzing search results...")

        prompt = f"""Analyze these search results for the query: "{query}"

{results_text}

Provide your analysis in YAML format:
```yaml
summary: >
    Brief summary of findings (2-3 sentences)
key_points:
    - First key point
    - Second key point
    - Third key point
follow_up_queries:
    - Suggested follow-up query 1
    - Suggested follow-up query 2
```
"""
        response = _llm_call(llm, model, prompt)
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        analysis = yaml.safe_load(yaml_str)

        assert "summary" in analysis, "Missing 'summary'"
        assert "key_points" in analysis, "Missing 'key_points'"
        return analysis

    def post(self, store, prep_result, exec_result):
        store["analysis"] = exec_result

        print("\n===== SEARCH ANALYSIS =====\n")
        print(f"Summary: {exec_result['summary']}\n")
        print("Key Points:")
        for point in exec_result.get("key_points", []):
            print(f"  - {point}")
        print("\nFollow-up Queries:")
        for q in exec_result.get("follow_up_queries", []):
            print(f"  - {q}")
        print("\n===========================\n")
        return "done"


@click.command()
@click.argument("query", default="What is quantum computing?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(query, provider, model):
    """Search the web and analyze results with an LLM."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    search = SearchNode()
    analyze = AnalyzeResultsNode()
    search.then("default", analyze)

    store = Store(
        data={"query": query, "search_results": [], "analysis": {}, "_llm": llm, "_model": model},
        name="tool_search",
    )

    flow = Flow(start=search)
    flow.run(store)


if __name__ == "__main__":
    main()
