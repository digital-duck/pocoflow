"""Utility: DuckDuckGo web search."""

from duckduckgo_search import DDGS


def search_web(query: str) -> str:
    results = DDGS().text(query, max_results=5)
    return "\n\n".join(
        f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
        for r in results
    )


if __name__ == "__main__":
    print(search_web("Who won the Nobel Prize in Physics 2024?"))
