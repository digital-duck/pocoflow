# PocoFlow Nested Batch

School grade processing with nested class/student directories.

## What It Shows

- **Nested batch pattern**: processes school -> class -> student hierarchy
- **No LLM needed**: pure data processing example
- **Replaces PocketFlow's nested BatchFlow**: loops inside exec() instead

## Run It

```bash
pip install -r requirements.txt
python main.py
```

## Data Structure

```
school/
  class_a/
    student1.txt    # grades: 85, 90, 78, 92, 88
    student2.txt    # grades: 72, 68, 75, 80, 70
  class_b/
    student3.txt    # grades: 95, 98, 92, 97, 94
    student4.txt    # grades: 60, 55, 65, 70, 58
```

## How It Works

```mermaid
flowchart LR
    Load[LoadAndProcessGrades] -->|report| Report[GenerateReport]
```

## Files

- `main.py` — single-file implementation
- `school/` — sample grade data
