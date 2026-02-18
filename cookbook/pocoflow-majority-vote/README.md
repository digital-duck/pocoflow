# PocoFlow Majority Vote

Consensus via repeated LLM sampling and majority vote. Runs the same question multiple times and picks the most common answer.

## Usage

```bash
python main.py --provider anthropic --tries 5
python main.py --provider ollama --model llama3.2 "What is 2+2?"
python main.py --provider openrouter --tries 3 "Your problem here"
```

## How it works

1. A `BatchNode` sends the same question to the LLM `N` times
2. Each response is parsed for a YAML-formatted answer
3. Failed attempts are gracefully skipped via `exec_fallback`
4. The most common answer wins (majority vote)
