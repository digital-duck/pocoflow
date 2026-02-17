"""Utility: call Anthropic Claude API for chat completions."""

import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-5-20250929"


def call_llm(messages: list[dict]) -> str:
    """Send a conversation to Claude and return the assistant reply."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=messages,
    )
    return response.content[0].text


if __name__ == "__main__":
    messages = [{"role": "user", "content": "In a few words, what's the meaning of life?"}]
    reply = call_llm(messages)
    print(f"Prompt:   {messages[0]['content']}")
    print(f"Response: {reply}")
