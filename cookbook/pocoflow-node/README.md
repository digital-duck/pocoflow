# PocoFlow Node

Demonstrates a single-node flow with LLM-powered text summarisation and automatic retry.

## What It Shows

- **prep/exec/post lifecycle**: the nano-ETL pattern
- **max_retries + retry_delay**: built-in resilience for transient API errors
- **Store**: typed shared state instead of raw dict
- **Multi-provider**: works with any supported LLM provider

## Run It

```bash
pip install -r requirements.txt

# Anthropic (default)
export ANTHROPIC_API_KEY="your-key"
python main.py --provider anthropic

# OpenAI
export OPENAI_API_KEY="your-key"
python main.py --provider openai

# Ollama (local, no API key needed)
python main.py --provider ollama --model llama3.2

# See all options
python main.py --help
```

## How It Works

```mermaid
flowchart LR
    summarize[SummarizeNode]
```

A single `SummarizeNode`:
1. **prep** — reads text from Store
2. **exec** — asks LLM to summarise in 10 words (retries up to 3x)
3. **post** — writes summary back to Store
