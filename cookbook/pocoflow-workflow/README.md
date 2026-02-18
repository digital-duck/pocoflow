# PocoFlow Workflow

An article writing pipeline: outline -> write sections -> apply style.

## What It Shows

- **3-node sequential workflow**: outline -> write -> style
- **YAML structured output**: LLM returns outline in YAML format
- **Batch-in-exec pattern**: WriteSections loops over sections inside exec() (replaces PocketFlow's BatchNode)
- **Retry**: GenerateOutline retries on YAML parse failures
- **Multi-provider**: works with any supported LLM provider

## Run It

```bash
pip install -r requirements.txt

# Anthropic (default)
export ANTHROPIC_API_KEY="your-key"
python main.py "Climate Change"

# Ollama (local)
python main.py --provider ollama --model llama3.2 "AI Safety"

# See all options
python main.py --help
```

## How It Works

```mermaid
flowchart LR
    Outline[GenerateOutline] --> Write[WriteSections]
    Write --> Style[ApplyStyle]
```

## Files

- `main.py` — flow wiring and CLI entry point
- `nodes.py` — 3 node implementations
