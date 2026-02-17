"""Utility: Anthropic Claude + DuckDuckGo search."""

import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from duckduckgo_search import DDGS

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-5-20250929"


def call_llm(prompt: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def search_web(query: str) -> str:
    results = DDGS().text(query, max_results=5)
    return "\n\n".join(
        f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
        for r in results
    )


if __name__ == "__main__":
    print("## Testing call_llm")
    print(call_llm("In a few words, what is the meaning of life?"))
    print("\n## Testing search_web")
    print(search_web("Who won the Nobel Prize in Physics 2024?"))
