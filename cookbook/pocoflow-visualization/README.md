# PocoFlow Visualization

Interactive visualization of PocoFlow workflow graphs using Mermaid diagrams and D3.js.

## What It Shows

- **Mermaid diagrams**: text-based flow visualization
- **D3.js interactive graphs**: draggable nodes with force-directed layout
- **Flow introspection**: walks the node/successor graph structure

## Run It

```bash
pip install -r requirements.txt
python main.py
```

This generates an interactive visualization in `./viz/` and opens it in your browser.

## How It Works

1. Creates an example PocoFlow graph
2. Generates a Mermaid diagram (printed to console)
3. Converts the graph to JSON for D3.js
4. Serves an interactive HTML visualization
