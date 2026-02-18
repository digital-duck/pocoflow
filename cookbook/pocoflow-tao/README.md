# PocoFlow TAO

Think-Action-Observe reasoning loop. The LLM thinks about what to do, an action node executes it, and an observer summarizes the result before looping back.

## Usage

```bash
python main.py --provider anthropic "What is quantum computing?"
python main.py --provider ollama --model llama3.2
python main.py --provider openrouter "Explain climate change"
```

## How it works

1. **ThinkNode** — LLM decides next action (search, calculate, or answer)
2. **ActionNode** — Executes the chosen action (simulated)
3. **ObserveNode** — LLM summarizes the action result
4. Loop back to ThinkNode until `is_final: true`
