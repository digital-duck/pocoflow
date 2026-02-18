# PocoFlow RAG

Retrieval-Augmented Generation with FAISS vector search.

## What It Shows

- **Two-phase pipeline**: offline indexing + online query
- **FAISS vector search**: efficient similarity search
- **Batch-in-exec pattern**: embed all chunks in a loop (replaces PocketFlow's BatchNode)
- **5 nodes across 2 flows**: ChunkDocuments, EmbedAndIndex, EmbedQuery, RetrieveDocuments, GenerateAnswer
- **Multi-provider**: LLM answer generation works with any supported provider

## Run It

```bash
pip install -r requirements.txt

# Requires OpenAI for embeddings + any LLM provider for answer generation
export OPENAI_API_KEY="your-key"

# Anthropic (default)
export ANTHROPIC_API_KEY="your-key"
python main.py --provider anthropic

# Ollama (local, still needs OpenAI for embeddings)
python main.py --provider ollama --model llama3.2

# See all options
python main.py --help
```

## How It Works

**Offline (indexing):**
```mermaid
flowchart LR
    Chunk[ChunkDocuments] --> Embed[EmbedAndIndex]
```

**Online (query):**
```mermaid
flowchart LR
    EmbedQ[EmbedQuery] --> Retrieve[RetrieveDocuments] --> Answer[GenerateAnswer]
```

## Files

- `main.py` — two-phase CLI entry point
- `nodes.py` — 5 node implementations
- `utils.py` — OpenAI embeddings + FAISS helpers
