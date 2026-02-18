# PocoFlow Communication

Demonstrates inter-node communication via the shared Store. Nodes read from and write to the Store to pass data between each other.

## Usage

```bash
python main.py
```

## How it works

1. `TextInputNode` reads user input and stores it
2. `WordCounterNode` reads the text and counts words
3. `ShowStatsNode` reads accumulated statistics and displays them
4. The flow loops back to `TextInputNode` for more input
5. Type `q` to exit
