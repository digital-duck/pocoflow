"""RAG nodes: chunk, embed, retrieve, answer."""

import numpy as np
from pocoflow import Node
from utils import call_llm, get_embedding, create_index, add_vectors, search_vectors


class ChunkDocuments(Node):
    """Split documents into smaller chunks."""

    def prep(self, store):
        return store["documents"]

    def exec(self, prep_result):
        chunks = []
        for doc in prep_result:
            # Simple sentence-based chunking
            sentences = doc.replace(". ", ".\n").split("\n")
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    chunks.append(sent)
        return chunks

    def post(self, store, prep_result, exec_result):
        store["chunks"] = exec_result
        print(f"  Chunked {len(prep_result)} documents into {len(exec_result)} chunks")
        return "default"


class EmbedAndIndex(Node):
    """Embed chunks and build FAISS index. Replaces PocketFlow's BatchNode."""

    def prep(self, store):
        return store["chunks"]

    def exec(self, prep_result):
        embeddings = []
        for i, chunk in enumerate(prep_result):
            emb = get_embedding(chunk)
            embeddings.append(emb)
            print(f"  Embedded chunk {i + 1}/{len(prep_result)}")

        embeddings_array = np.array(embeddings, dtype="float32")
        index = create_index(embeddings_array.shape[1])
        add_vectors(index, embeddings_array)
        return index

    def post(self, store, prep_result, exec_result):
        store["index"] = exec_result
        store["chunk_texts"] = prep_result
        print(f"  Built FAISS index with {len(prep_result)} vectors")
        return "default"


class EmbedQuery(Node):
    def prep(self, store):
        return store["question"]

    def exec(self, prep_result):
        return get_embedding(prep_result)

    def post(self, store, prep_result, exec_result):
        store["query_embedding"] = exec_result
        return "default"


class RetrieveDocuments(Node):
    def prep(self, store):
        return {
            "query_embedding": store["query_embedding"],
            "index": store["index"],
            "chunk_texts": store["chunk_texts"],
        }

    def exec(self, prep_result):
        indices, distances = search_vectors(
            prep_result["index"],
            np.array([prep_result["query_embedding"]], dtype="float32"),
            k=3,
        )
        results = []
        for idx, dist in zip(indices, distances):
            if idx < len(prep_result["chunk_texts"]):
                results.append({
                    "text": prep_result["chunk_texts"][idx],
                    "distance": float(dist),
                })
        return results

    def post(self, store, prep_result, exec_result):
        store["retrieved_chunks"] = exec_result
        for i, r in enumerate(exec_result):
            print(f"  Retrieved [{i+1}] (dist={r['distance']:.4f}): {r['text'][:60]}...")
        return "default"


class GenerateAnswer(Node):
    def prep(self, store):
        context = "\n".join(r["text"] for r in store["retrieved_chunks"])
        return store["question"], context

    def exec(self, prep_result):
        question, context = prep_result
        prompt = f"""Answer the question based on the provided context.

Context:
{context}

Question: {question}

Answer concisely based only on the context provided."""
        return call_llm(prompt)

    def post(self, store, prep_result, exec_result):
        store["answer"] = exec_result
        return "done"
