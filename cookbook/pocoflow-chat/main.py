"""PocoFlow Chat — simple conversational chatbot using Anthropic Claude.

Run:
    export ANTHROPIC_API_KEY="your-key"
    python cookbook/pocoflow-chat/main.py
"""

from pocoflow import Node, Flow, Store
from utils import call_llm


class ChatNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        # First run: print welcome banner
        if not store["messages"]:
            print("Welcome to PocoFlow Chat!  Type 'exit' to quit.\n")

        user_input = input("You: ")

        if user_input.strip().lower() == "exit":
            return None

        store["messages"].append({"role": "user", "content": user_input})
        return store["messages"]

    def exec(self, messages):
        if messages is None:
            return None
        return call_llm(messages)

    def post(self, store, prep_result, exec_result):
        if prep_result is None or exec_result is None:
            print("\nGoodbye!")
            return "exit"

        print(f"\nAssistant: {exec_result}\n")
        store["messages"].append({"role": "assistant", "content": exec_result})
        return "continue"


if __name__ == "__main__":
    chat = ChatNode()
    chat.then("continue", chat)          # self-loop

    store = Store(
        data={"messages": []},
        name="chat",
    )

    flow = Flow(start=chat)
    flow.run(store)
