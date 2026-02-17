"""PocoFlow RAG — retrieval-augmented generation.

Demonstrates: two-phase flow (offline indexing + online query), FAISS vector search.
Original PocketFlow uses BatchNode for chunking/embedding; PocoFlow loops in exec().
"""

from pocoflow import Flow, Store
from nodes import ChunkDocuments, EmbedAndIndex, EmbedQuery, RetrieveDocuments, GenerateAnswer


SAMPLE_TEXTS = [
    "The solar system consists of the Sun and the celestial objects bound to it by gravity. "
    "The eight planets, in order from the Sun, are Mercury, Venus, Earth, Mars, Jupiter, "
    "Saturn, Uranus, and Neptune. Earth is the third planet and the only one known to harbor life.",

    "Machine learning is a subset of artificial intelligence that enables systems to learn "
    "from data. Supervised learning uses labeled examples, while unsupervised learning finds "
    "patterns in unlabeled data. Deep learning uses neural networks with many layers.",

    "The water cycle describes the continuous movement of water on Earth. Water evaporates "
    "from oceans and lakes, forms clouds through condensation, falls as precipitation, "
    "and flows back to the ocean through rivers and groundwater.",
]


def run_offline_indexing():
    """Phase 1: chunk documents and build FAISS index."""
    chunk = ChunkDocuments()
    embed = EmbedAndIndex()
    chunk.then("default", embed)

    store = Store(
        data={"documents": SAMPLE_TEXTS, "chunks": [], "index": None, "chunk_texts": []},
        name="rag_offline",
    )

    print("=== Phase 1: Offline Indexing ===\n")
    flow = Flow(start=chunk)
    flow.run(store)
    print(f"Indexed {len(store['chunk_texts'])} chunks.\n")
    return store


def run_online_query(offline_store):
    """Phase 2: embed query, retrieve, generate answer."""
    embed_q = EmbedQuery()
    retrieve = RetrieveDocuments()
    answer = GenerateAnswer()

    embed_q.then("default", retrieve)
    retrieve.then("default", answer)

    question = input("Ask a question (or press Enter for default): ").strip()
    if not question:
        question = "What planets are in the solar system?"

    store = Store(
        data={
            "question": question,
            "index": offline_store["index"],
            "chunk_texts": offline_store["chunk_texts"],
            "retrieved_chunks": [],
            "answer": "",
        },
        name="rag_online",
    )

    print(f"\n=== Phase 2: Online Query ===\n")
    print(f"Question: {question}\n")
    flow = Flow(start=embed_q)
    flow.run(store)
    print(f"\nAnswer: {store['answer']}")


def main():
    offline_store = run_offline_indexing()
    run_online_query(offline_store)


if __name__ == "__main__":
    main()
