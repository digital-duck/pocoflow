# PocoFlow Async Basic — Recipe Finder

An interactive recipe finder demonstrating AsyncNode with async exec.

## What It Shows

- **AsyncNode**: `exec_async()` for non-blocking I/O
- **Multi-node flow**: fetch → suggest → approve
- **Retry loop**: reject sends you back to suggest

## Run It

```bash
pip install -r requirements.txt
python main.py
```

## How It Works

```mermaid
flowchart LR
    fetch[FetchRecipesNode] -->|suggest| suggest[SuggestRecipeNode]
    suggest -->|approve| approve[GetApprovalNode]
    approve -->|retry| suggest
    approve -->|accept| END
```

Uses mock async functions (no API keys needed).
