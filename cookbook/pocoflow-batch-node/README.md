# PocoFlow Batch Node

CSV chunk processing: reads a large CSV and computes aggregate statistics.

## What It Shows

- **Batch-over-nodes pattern**: processes CSV in chunks inside exec()
- **Replaces PocketFlow's BatchNode**: loop inside exec() instead of prep() returning items
- **2-node flow**: CSVProcessor -> ShowStats

## Run It

```bash
pip install -r requirements.txt
python main.py
```

The script auto-generates a 10,000-row `data/sales.csv` if it doesn't exist.

## How It Works

```mermaid
flowchart LR
    CSV[CSVProcessor] -->|show_stats| Stats[ShowStats]
```

## Files

- `main.py` — single-file implementation
