# PocoFlow Tool Database

SQLite database operations as a PocoFlow pipeline.

## Usage

```bash
python main.py
python main.py --title "My Task" --description "Important work"
```

## How it works

1. **InitDatabaseNode** — Creates the tasks table if not exists
2. **CreateTaskNode** — Inserts a new task record
3. **ListTasksNode** — Queries and returns all tasks

The SQLite database is stored as `tasks.db` in the example directory.
