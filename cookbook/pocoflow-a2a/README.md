# PocoFlow A2A

Agent-to-agent pattern — a research agent that decides whether to search or answer.

## Usage

```bash
python main.py --provider anthropic "What is quantum computing?"
python main.py --provider ollama --model llama3.2
python main.py --provider openrouter "Explain climate change"
```

## How it works

1. **DecideActionNode** — LLM decides: search for more info or answer directly
2. **SearchWebNode** — Performs web search (simulated; plug in real search)
3. **AnswerNode** — LLM generates final answer from accumulated research
4. Search results loop back to DecideActionNode for iterative research
