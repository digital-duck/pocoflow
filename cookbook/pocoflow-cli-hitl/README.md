# PocoFlow CLI HITL

Human-in-the-loop joke generator. The LLM generates jokes and the user approves or rejects them interactively.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2
python main.py --provider openrouter
```

## How it works

1. **GetTopicNode** — Asks the user for a joke topic
2. **GenerateJokeNode** — LLM generates a one-liner joke (avoiding previously rejected jokes)
3. **GetFeedbackNode** — User approves or rejects; rejected jokes loop back to generate
