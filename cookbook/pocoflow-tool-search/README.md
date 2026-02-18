# PocoFlow Tool Search

Web search with LLM-powered analysis of results.

## What It Shows

- **Tool integration**: web search via DuckDuckGo
- **YAML structured output**: LLM returns analysis in parsed YAML
- **2-node pipeline**: SearchNode → AnalyzeResultsNode
- **Multi-provider**: works with any supported LLM provider

## Run It

```bash
pip install -r requirements.txt

# Anthropic (default)
export ANTHROPIC_API_KEY="your-key"
python main.py "What is quantum computing?"

# Ollama (local)
python main.py --provider ollama --model llama3.2 "latest news on AI"

# See all options
python main.py --help
```

## How It Works

```mermaid
graph LR
    A[SearchNode] --> B[AnalyzeResultsNode]
    B --> C[End]
```

- **SearchNode** — runs a web search via DuckDuckGo, returns top results
- **AnalyzeResultsNode** — LLM summarizes findings, extracts key points, suggests follow-up queries (YAML output)
