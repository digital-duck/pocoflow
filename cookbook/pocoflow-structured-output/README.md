# PocoFlow Structured Output — Resume Parser

Extracts structured data from a resume using LLM prompt engineering and YAML parsing.

## What It Shows

- **Structured LLM output**: prompt engineering for YAML
- **Validation with assertions**: retry on malformed output
- **max_retries**: automatically re-attempts on parse failure

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
pip install -r requirements.txt
python main.py
```

## How It Works

```mermaid
flowchart LR
    parser[ResumeParserNode]
```

A single `ResumeParserNode`:
1. **prep** — reads resume text and target skills from Store
2. **exec** — sends resume to Claude, parses YAML response, validates structure
3. **post** — stores structured data, prints results

If the LLM returns malformed YAML or missing fields, the assertion fails and
PocoFlow automatically retries (up to 3 times).
