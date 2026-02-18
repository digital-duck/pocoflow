# PocoFlow FastAPI HITL

Human-in-the-loop review workflow via FastAPI. Submit text, LLM processes it, then a human approves or rejects.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2
```

## API Endpoints

- `POST /submit` — Submit text for processing (`{"data": "your text"}`)
- `GET /stream/{task_id}` — SSE stream for status updates
- `POST /feedback/{task_id}` — Approve or reject (`{"feedback": "approved"}`)

## How it works

1. **ProcessNode** — LLM improves the submitted text
2. **ReviewNode** (AsyncNode) — Waits for human feedback via API
3. **ResultNode** — Finalizes on approval; rejected loops back to ProcessNode
