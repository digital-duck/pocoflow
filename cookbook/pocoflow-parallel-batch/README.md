# PocoFlow Parallel Batch

Compares sequential vs parallel async batch processing.

## What It Shows

- **Sequential**: AsyncNode processes items one at a time in a loop
- **Parallel**: AsyncNode uses asyncio.gather for concurrent execution
- **Speedup**: 3 items x 1s each = ~3s sequential vs ~1s parallel
- **No external deps**: uses simulated async LLM calls

## Run It

```bash
pip install -r requirements.txt
python main.py
```

## How It Works

Both approaches use a single AsyncNode. The difference is in exec_async():
- **Sequential**: `for item in items: await process(item)`
- **Parallel**: `await asyncio.gather(*[process(item) for item in items])`

## Files

- `main.py` — single-file implementation comparing both approaches
