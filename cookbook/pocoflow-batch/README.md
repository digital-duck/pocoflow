# PocoFlow Batch — Document Translation

Translates a markdown document into multiple languages using Claude.

## What It Shows

- **Batch processing** pattern (loop inside exec)
- **Retry** for transient API errors
- **File I/O** in post phase

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
pip install -r requirements.txt
python main.py
```

## How It Works

```mermaid
flowchart LR
    translate[TranslateNode]
```

A single `TranslateNode` that processes a list of languages sequentially:
1. **prep** — builds `(text, language)` pairs
2. **exec** — translates each pair via Claude
3. **post** — writes each translation to a file
