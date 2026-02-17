# PocoFlow RAG

Retrieval-Augmented Generation with FAISS vector search.

## What It Shows

- **Two-phase pipeline**: offline indexing + online query
- **FAISS vector search**: efficient similarity search
- **Batch-in-exec pattern**: embed all chunks in a loop (replaces PocketFlow's BatchNode)
- **5 nodes across 2 flows**: ChunkDocuments, EmbedAndIndex, EmbedQuery, RetrieveDocuments, GenerateAnswer

## Run It

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"    # for embeddings
pip install -r requirements.txt
python main.py
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

- `main.py` — two-phase entry point
- `nodes.py` — 5 node implementations
- `utils.py` — Anthropic Claude + OpenAI embeddings + FAISS helpers
