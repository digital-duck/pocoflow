# PocoFlow Workflow

An article writing pipeline: outline -> write sections -> apply style.

## What It Shows

- **3-node sequential workflow**: outline -> write -> style
- **YAML structured output**: LLM returns outline in YAML format
- **Batch-in-exec pattern**: WriteSections loops over sections inside exec() (replaces PocketFlow's BatchNode)
- **Retry**: GenerateOutline retries on YAML parse failures

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
pip install -r requirements.txt
python main.py
# or with a custom topic:
python main.py Climate Change
```

## How It Works

```mermaid
flowchart LR
    Outline[GenerateOutline] --> Write[WriteSections]
    Write --> Style[ApplyStyle]
```

## Files

- `main.py` — flow wiring and entry point
- `nodes.py` — 3 node implementations
- `utils.py` — Anthropic Claude wrapper
