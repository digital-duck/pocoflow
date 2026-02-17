"""Utility: Anthropic Claude + OpenAI embeddings + FAISS helpers."""

import os
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "claude-sonnet-4-5-20250929"


def call_llm(prompt: str) -> str:
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
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
    print("Testing call_llm...")
    print(call_llm("What is RAG in AI?"))
    print("\nTesting get_embedding...")
    emb = get_embedding("test embedding")
    print(f"Embedding dimension: {len(emb)}")
