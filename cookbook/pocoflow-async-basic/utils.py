"""Async utilities for the recipe finder example (mock implementations)."""

import asyncio


async def fetch_recipes(ingredient: str) -> list[str]:
    """Simulate async API call to fetch recipes."""
    print(f"Fetching recipes for {ingredient}...")
    await asyncio.sleep(1)  # simulate network delay
    return [
        f"{ingredient} Stir Fry",
        f"Grilled {ingredient} with Herbs",
        f"Baked {ingredient} with Vegetables",
    ]


async def call_llm_async(prompt: str) -> str:
    """Simulate async LLM call."""
    print("\nSuggesting best recipe...")
    await asyncio.sleep(1)  # simulate LLM latency
    # Mock: pick the second recipe from the prompt
    recipes = prompt.split(": ")[1].split(", ")
    suggestion = recipes[1] if len(recipes) > 1 else recipes[0]
    print(f"How about: {suggestion}")
    return suggestion
