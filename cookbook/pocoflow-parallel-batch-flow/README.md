# PocoFlow Parallel Batch Flow

Parallel image processing: compares sequential vs parallel filter application.

## What It Shows

- **Sequential vs Parallel**: side-by-side timing comparison
- **AsyncNode + asyncio.gather**: parallel batch-over-flows pattern
- **Replaces PocketFlow's AsyncParallelBatchFlow**: single AsyncNode instead

## Setup

Place sample images in `images/` directory:
```
images/
  cat.jpg
  dog.jpg
  bird.jpg
```

## Run It

```bash
pip install -r requirements.txt
python main.py
```

## How It Works

Both approaches process 9 image-filter combinations (3 images x 3 filters).
Each has a simulated 0.1s async I/O delay:
- **Sequential**: ~0.9s (9 x 0.1s)
- **Parallel**: ~0.1s (all 9 run concurrently)

## Files

- `main.py` — single-file implementation comparing both approaches
