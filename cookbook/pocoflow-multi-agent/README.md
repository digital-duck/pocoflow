# PocoFlow Multi-Agent

Two LLM agents play Taboo: one gives hints, the other guesses the target word.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2 --target "serendipity" --forbidden "luck,chance,accident,happy,discover"
python main.py --provider openrouter --rounds 5
```

## How it works

1. **HinterNode** — LLM generates a hint (max 5 words) without using forbidden words
2. **GuesserNode** — LLM guesses based on the hint and past wrong guesses
3. Agents take turns until the word is guessed or max rounds reached
4. Communication happens via async queues in the shared Store
