# PocoFlow MCP

Model Context Protocol pattern — LLM discovers and calls tools dynamically.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2 "What is 42 times 17?"
python main.py --provider openrouter "Divide 100 by 7"
```

## How it works

1. **GetToolsNode** — Lists available tools (add, subtract, multiply, divide)
2. **DecideToolNode** — LLM analyzes the question and selects a tool + parameters
3. **ExecuteToolNode** — Calls the selected tool and returns the result

Tools are defined locally; extend by connecting to an actual MCP server.
