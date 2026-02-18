# PocoFlow FastAPI Background

Article generator running as a background task with Server-Sent Events (SSE) for progress tracking.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2 --port 8080
```

Then POST to `/start-job` with a `topic` form field and GET `/progress/{job_id}` for SSE updates.

## How it works

1. **GenerateOutlineNode** — LLM creates a 3-section outline (33% progress)
2. **WriteContentNode** — LLM writes each section (33-66% progress)
3. **ApplyStyleNode** — LLM rewrites in engaging style (100% progress)
4. Progress updates stream via SSE to the client
