# PocoFlow Code Generator

Test-driven code generation: generates tests, implements, runs, and revises.

## What It Shows

- **4-node pipeline**: generate tests -> implement -> run tests -> revise (loop)
- **Revision loop**: up to 3 attempts to fix failing tests
- **Safe code execution**: runs generated code in subprocess with timeout
- **YAML structured output**: test cases in YAML format
- **Batch-in-exec pattern**: RunTests loops over test cases (replaces PocketFlow's BatchNode)

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
pip install -r requirements.txt
python main.py
# or with a custom requirement:
python main.py "Write a function called fibonacci that returns the nth fibonacci number"
```

## How It Works

```mermaid
flowchart LR
    Gen[GenerateTestCases] --> Impl[ImplementFunction]
    Impl --> Run[RunTests]
    Run -->|success| End((end))
    Run -->|failure| Rev[Revise]
    Rev --> Run
```

## Files

- `main.py` — flow wiring and entry point
- `nodes.py` — 4 node implementations
- `utils.py` — Anthropic Claude + safe Python execution
