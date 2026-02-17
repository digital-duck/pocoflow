"""PocoFlow Agent — research agent with web search.

Demonstrates: multi-node agent loop, YAML structured output, DuckDuckGo search.
"""

import sys
from pocoflow import Flow, Store
from nodes import DecideAction, SearchWeb, AnswerQuestion


def main():
    question = "Who won the Nobel Prize in Physics 2024?"
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            question = arg[2:]
            break

    decide = DecideAction()
    search = SearchWeb()
    answer = AnswerQuestion()

    decide.then("search", search)
    decide.then("answer", answer)
    search.then("decide", decide)
    # "done" has no successor -> flow ends

    store = Store(
        data={"question": question, "context": "", "answer": ""},
        name="research_agent",
    )

    print(f"Processing question: {question}")
    flow = Flow(start=decide)
    flow.run(store)
    print(f"\nFinal Answer:\n{store['answer']}")


if __name__ == "__main__":
    main()
