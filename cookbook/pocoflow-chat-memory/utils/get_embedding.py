"""Utility: generate text embeddings via OpenAI."""

import os
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def get_embedding(text: str) -> np.ndarray:
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text,
    )
    return np.array(response.data[0].embedding, dtype=np.float32)


if __name__ == "__main__":
    emb = get_embedding("Hello world")
    print(f"Embedding shape: {emb.shape}")
