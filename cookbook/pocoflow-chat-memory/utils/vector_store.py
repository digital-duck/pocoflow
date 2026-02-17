"""Utility: FAISS vector index helpers."""

import numpy as np
import faiss


def create_index(dimension: int = 1536):
    return faiss.IndexFlatL2(dimension)


def add_vector(index, vector) -> int:
    vector = np.array(vector).reshape(1, -1).astype(np.float32)
    index.add(vector)
    return index.ntotal - 1


def search_vectors(index, query_vector, k: int = 1):
    k = min(k, index.ntotal)
    if k == 0:
        return [], []
    query_vector = np.array(query_vector).reshape(1, -1).astype(np.float32)
    distances, indices = index.search(query_vector, k)
    return indices[0].tolist(), distances[0].tolist()


if __name__ == "__main__":
    idx = create_index(dimension=3)
    items = []
    for i in range(5):
        v = np.random.random(3)
        pos = add_vector(idx, v)
        items.append(f"Item {i}")
        print(f"Added at position {pos}")
    q = np.random.random(3)
    found_idx, dists = search_vectors(idx, q, k=2)
    print(f"Found: {[items[i] for i in found_idx]}, distances: {dists}")
