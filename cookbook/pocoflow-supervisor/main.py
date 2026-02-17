"""PocoFlow Supervisor — supervised research agent.

Demonstrates: supervisor pattern, answer validation, retry loop.
Original PocketFlow uses Flow-as-Node; here we flatten to a single flow.
"""

import sys
from pocoflow import Flow, Store
from nodes import DecideAction, SearchWeb, UnreliableAnswerNode, SupervisorNode


def main():
    question = "Who won the Nobel Prize in Physics 2024?"
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            question = arg[2:]
            break

    decide = DecideAction()
    search = SearchWeb()
    answer = UnreliableAnswerNode()
    supervisor = SupervisorNode()

    decide.then("search", search)
    decide.then("answer", answer)
    search.then("decide", decide)
    answer.then("check", supervisor)
    supervisor.then("retry", decide)  # rejected -> restart research
    # "approved" has no successor -> flow ends

    store = Store(
        data={"question": question, "context": "", "answer": ""},
        name="supervised_agent",
    )

    print(f"Processing question: {question}")
    flow = Flow(start=decide)
    flow.run(store)
    print(f"\nFinal Answer:\n{store['answer']}")


if __name__ == "__main__":
    main()
