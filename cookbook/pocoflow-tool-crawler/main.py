"""PocoFlow Tool Crawler — web crawling with LLM content analysis.

Demonstrates: tool integration, web crawling, batch analysis, report generation.
"""

import os
import yaml
import click
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


def _llm_call(llm, model, prompt):
    response = llm.call(prompt, model=model)
    if not response.success:
        raise RuntimeError(f"LLM failed: {response.error_history}")
    return response.content


def crawl_website(base_url, max_pages=5):
    """Crawl a website and extract content from pages."""
    visited = set()
    to_visit = [base_url]
    results = []
    base_domain = urlparse(base_url).netloc

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        try:
            print(f"  Crawling: {url}")
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            text = soup.get_text(separator="\n", strip=True)
            title = soup.title.string if soup.title else ""

            # Extract same-domain links
            links = []
            for a in soup.find_all("a", href=True):
                abs_url = urljoin(url, a["href"])
                if urlparse(abs_url).netloc == base_domain and abs_url not in visited:
                    links.append(abs_url)

            visited.add(url)
            results.append({"url": url, "title": title, "text": text[:3000], "links": links})
            to_visit.extend([l for l in links if l not in visited and l not in to_visit])
        except Exception as e:
            print(f"  Error crawling {url}: {e}")

    return results


class CrawlNode(Node):
    def prep(self, store):
        return store["base_url"], store.get("max_pages", 5)

    def exec(self, prep_result):
        base_url, max_pages = prep_result
        print(f"Crawling {base_url} (max {max_pages} pages)...")
        return crawl_website(base_url, max_pages)

    def post(self, store, prep_result, exec_result):
        store["crawl_results"] = exec_result
        print(f"Crawled {len(exec_result)} pages")
        return "default"


class AnalyzeNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["crawl_results"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        pages, llm, model = prep_result
        analyses = []
        for page in pages:
            print(f"  Analyzing: {page['url']}")
            prompt = f"""Analyze this webpage content:

Title: {page['title']}
URL: {page['url']}
Content: {page['text'][:2000]}

Provide your analysis in YAML format:
```yaml
summary: >
    Brief summary (2-3 sentences)
topics:
    - topic 1
    - topic 2
content_type: article/product/docs/other
```"""
            try:
                response = _llm_call(llm, model, prompt)
                yaml_str = response.split("```yaml")[1].split("```")[0].strip()
                analysis = yaml.safe_load(yaml_str)
                assert "summary" in analysis
            except Exception:
                analysis = {"summary": "Analysis failed", "topics": [], "content_type": "unknown"}

            analyses.append({**page, "analysis": analysis})
        return analyses

    def post(self, store, prep_result, exec_result):
        store["analyzed_results"] = exec_result
        return "default"


class ReportNode(Node):
    def prep(self, store):
        return store["analyzed_results"]

    def exec(self, prep_result):
        if not prep_result:
            return "No results to report."

        lines = [f"Analysis Report", f"Total pages analyzed: {len(prep_result)}", ""]
        for page in prep_result:
            analysis = page.get("analysis", {})
            lines.append(f"Page: {page['url']}")
            lines.append(f"Title: {page['title']}")
            lines.append(f"Summary: {analysis.get('summary', 'N/A')}")
            lines.append(f"Topics: {', '.join(analysis.get('topics', []))}")
            lines.append(f"Type: {analysis.get('content_type', 'unknown')}")
            lines.append("-" * 60)
        return "\n".join(lines)

    def post(self, store, prep_result, exec_result):
        store["report"] = exec_result
        print(f"\n{'=' * 60}")
        print(exec_result)
        print(f"{'=' * 60}")
        return "done"


@click.command()
@click.argument("url")
@click.option("--max-pages", default=3, help="Maximum pages to crawl")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(url, max_pages, provider, model):
    """Crawl a website and analyze its content with an LLM."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    crawl = CrawlNode()
    analyze = AnalyzeNode()
    report = ReportNode()
    crawl.then("default", analyze)
    analyze.then("default", report)

    store = Store(
        data={
            "base_url": url,
            "max_pages": max_pages,
            "crawl_results": [],
            "analyzed_results": [],
            "report": "",
            "_llm": llm,
            "_model": model,
        },
        name="tool_crawler",
    )

    flow = Flow(start=crawl)
    flow.run(store)


if __name__ == "__main__":
    main()
