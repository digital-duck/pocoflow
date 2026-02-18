# Chain-of-Thought Thinking

This example demonstrates chain-of-thought reasoning using a single self-looping PocoFlow node. The LLM iteratively builds and refines a structured plan via YAML output, evaluating each previous step before proceeding to the next.

Based on: [Build Chain-of-Thought From Scratch - Tutorial for Dummies](https://zacharyhuang.substack.com/p/build-chain-of-thought-from-scratch)

## Features

- Improves model reasoning on complex problems by enforcing structured step-by-step thinking.
- Maintains a living plan with steps, sub-steps, statuses, and results.
- Self-corrects through explicit evaluation of prior thoughts.
- Works with any provider supported by `UniversalLLMProvider` (Anthropic, OpenAI, Gemini, OpenRouter, Ollama).

## How It Works

A single `ChainOfThoughtNode` loops on itself until the problem is solved:

```
flowchart LR
    cot[ChainOfThoughtNode] -->|"continue"| cot
```

Each iteration:

1. **prep** -- gathers the question, accumulated thoughts, and LLM config from the store.
2. **exec** -- builds a prompt with all previous thoughts and the current plan, calls the LLM, and parses the structured YAML response.
3. **post** -- appends the new thought, prints progress, and returns `"continue"` (loop) or `"end"` (done).

The YAML response from the LLM contains:

- `current_thinking` -- the reasoning for this step.
- `planning` -- a list of step dicts (`description`, `status`, optional `result`, `mark`, `sub_steps`).
- `next_thought_needed` -- boolean flag; `false` triggers termination.

## Getting Started

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set your API key:**

   ```bash
   export ANTHROPIC_API_KEY="your-key"
   # or OPENAI_API_KEY, GEMINI_API_KEY, etc.
   ```

3. **Run the default example:**

   ```bash
   python main.py
   ```

   The default question is a probability puzzle:

   > You keep rolling a fair die until you roll three, four, five in that order consecutively on three rolls. What is the probability that you roll the die an odd number of times?

4. **Run with a custom question:**

   ```bash
   python main.py "What is the sum of all prime numbers less than 100?"
   ```

5. **Use a different provider/model:**

   ```bash
   python main.py --provider openai --model gpt-4o "Your question here"
   ```
