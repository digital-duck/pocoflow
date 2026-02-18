# PocoFlow Tool Embeddings

Generate text embeddings using OpenAI's embeddings API.

## What It Shows

- **OpenAI embeddings**: generates vector representations of text
- **Tool integration**: wraps API calls in a PocoFlow node
- **Single-node flow**: minimal example of tool usage

## Run It

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
python main.py "Your text here"
```

## How It Works

```mermaid
flowchart LR
    Embed[EmbeddingNode] --> Done[End]
```

- **EmbeddingNode** — calls OpenAI's text-embedding-ada-002 model to generate embeddings
