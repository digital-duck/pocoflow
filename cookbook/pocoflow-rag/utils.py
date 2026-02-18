"""Utility: OpenAI embeddings + FAISS helpers."""

import os
import numpy as np
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from openai import OpenAI

_openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def get_embedding(text: str) -> list[float]:
    response = _openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def create_index(dimension: int):
    import faiss
    return faiss.IndexFlatL2(dimension)


def add_vectors(index, vectors: np.ndarray):
    index.add(vectors)


def search_vectors(index, query: np.ndarray, k: int = 3):
    distances, indices = index.search(query, k)
    return indices[0].tolist(), distances[0].tolist()


if __name__ == "__main__":
    print("Testing get_embedding...")
    emb = get_embedding("test embedding")
    print(f"Embedding dimension: {len(emb)}")
