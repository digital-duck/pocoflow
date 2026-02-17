"""PocoFlow Chat with Memory — sliding window + vector retrieval.

Demonstrates: 4-node flow, embeddings, FAISS vector search, conversation archival.
"""

from pocoflow import Flow, Store
from nodes import GetUserQuestionNode, RetrieveNode, AnswerNode, EmbedNode


def main():
    question = GetUserQuestionNode()
    retrieve = RetrieveNode()
    answer = AnswerNode()
    embed = EmbedNode()

    question.then("retrieve", retrieve)
    retrieve.then("answer", answer)
    answer.then("question", question)
    answer.then("embed", embed)
    embed.then("question", question)
    # "exit" has no successor → flow ends

    store = Store(data={"messages": []}, name="chat_memory")

    print("=" * 50)
    print("PocoFlow Chat with Memory")
    print("=" * 50)
    print("Keeps 3 most recent conversation pairs.")
    print("Archives older ones and retrieves relevant context.")
    print("Type 'exit' to quit.")
    print("=" * 50)

    flow = Flow(start=question)
    flow.run(store)


if __name__ == "__main__":
    main()
