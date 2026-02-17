"""Chat memory nodes: question, retrieve, answer, embed."""

from pocoflow import Node
from utils.call_llm import call_llm
from utils.get_embedding import get_embedding
from utils.vector_store import create_index, add_vector, search_vectors


class GetUserQuestionNode(Node):
    def prep(self, store):
        if "messages" not in store.as_dict():
            store["messages"] = []
        return None

    def exec(self, prep_result):
        return input("\nYou: ")

    def post(self, store, prep_result, exec_result):
        user_input = exec_result
        if user_input.strip().lower() == "exit":
            print("\nGoodbye!")
            return "exit"

        store["messages"].append({"role": "user", "content": user_input})
        return "retrieve"


class RetrieveNode(Node):
    def prep(self, store):
        if not store.get("messages"):
            return None

        latest_user = next(
            (m for m in reversed(store["messages"]) if m["role"] == "user"),
            {"content": ""},
        )

        if "vector_index" not in store.as_dict() or not store.get("vector_items"):
            return None

        return {
            "query": latest_user["content"],
            "vector_index": store["vector_index"],
            "vector_items": store["vector_items"],
        }

    def exec(self, prep_result):
        if not prep_result:
            return None

        query = prep_result["query"]
        print(f"  Finding relevant context for: {query[:40]}...")

        query_embedding = get_embedding(query)
        indices, distances = search_vectors(
            prep_result["vector_index"], query_embedding, k=1
        )
        if not indices:
            return None

        return {
            "conversation": prep_result["vector_items"][indices[0]],
            "distance": distances[0],
        }

    def post(self, store, prep_result, exec_result):
        if exec_result:
            store["retrieved_conversation"] = exec_result["conversation"]
            print(f"  Retrieved past conversation (distance: {exec_result['distance']:.4f})")
        else:
            store["retrieved_conversation"] = None
        return "answer"


class AnswerNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        messages = list(store["messages"])  # copy
        retrieved = store.get("retrieved_conversation")

        if retrieved:
            context = "\n".join(
                f"{m['role'].title()}: {m['content']}" for m in retrieved
            )
            system_note = {
                "role": "user",
                "content": f"[Context from earlier conversation:\n{context}]",
            }
            # Insert before the latest user message
            messages.insert(-1, system_note)
            messages.insert(-1, {"role": "assistant", "content": "Got it, I'll keep that in mind."})

        return messages

    def exec(self, prep_result):
        return call_llm(prep_result)

    def post(self, store, prep_result, exec_result):
        print(f"\nAssistant: {exec_result}")
        store["messages"].append({"role": "assistant", "content": exec_result})

        # Archive oldest pair when window exceeds 6 messages (3 pairs)
        if len(store["messages"]) > 6:
            return "embed"
        return "question"


class EmbedNode(Node):
    def prep(self, store):
        if len(store["messages"]) <= 6:
            return None
        oldest_pair = store["messages"][:2]
        store["messages"] = store["messages"][2:]
        return oldest_pair

    def exec(self, prep_result):
        if not prep_result:
            return None
        user_msg = next((m for m in prep_result if m["role"] == "user"), {"content": ""})
        asst_msg = next((m for m in prep_result if m["role"] == "assistant"), {"content": ""})
        combined = f"User: {user_msg['content']} Assistant: {asst_msg['content']}"
        return {"conversation": prep_result, "embedding": get_embedding(combined)}

    def post(self, store, prep_result, exec_result):
        if not exec_result:
            return "question"

        if "vector_index" not in store.as_dict():
            store["vector_index"] = create_index()
            store["vector_items"] = []

        pos = add_vector(store["vector_index"], exec_result["embedding"])
        store["vector_items"].append(exec_result["conversation"])
        print(f"  Archived conversation at position {pos} ({len(store['vector_items'])} total)")
        return "question"
