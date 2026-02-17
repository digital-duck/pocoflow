"""Utility: Anthropic Claude + safe Python execution."""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

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


def execute_python(code: str, timeout: int = 10) -> str:
    """Execute Python code in a subprocess and return output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.returncode != 0:
                output += result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    print("Testing call_llm...")
    print(call_llm("Write a one-line Python function that adds two numbers"))
    print("\nTesting execute_python...")
    print(execute_python("print('Hello from subprocess!')"))
