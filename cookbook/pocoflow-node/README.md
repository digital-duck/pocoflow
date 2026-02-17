# PocoFlow Node

Demonstrates a single-node flow with LLM-powered text summarisation and automatic retry.

## What It Shows

- **prep/exec/post lifecycle**: the nano-ETL pattern
- **max_retries + retry_delay**: built-in resilience for transient API errors
- **Store**: typed shared state instead of raw dict

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
pip install -r requirements.txt
python main.py
```

## How It Works

```mermaid
flowchart LR
    summarize[SummarizeNode]
```

A single `SummarizeNode`:
1. **prep** — reads text from Store
2. **exec** — asks Claude to summarise in 10 words (retries up to 3x)
3. **post** — writes summary back to Store
