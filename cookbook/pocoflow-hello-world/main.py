"""PocoFlow Hello World — minimal single-node LLM flow.

Demonstrates: one Node, prep/exec/post lifecycle, Store, Flow.
"""

import sys
from pocoflow import Node, Flow, Store
from utils import call_llm


class AnswerNode(Node):
    def prep(self, store):
        return store["question"]

    def exec(self, prep_result):
        return call_llm(
            f"Answer this question concisely:\n{prep_result}"
        )

    def post(self, store, prep_result, exec_result):
        store["answer"] = exec_result
        print(f"\nAnswer: {exec_result}")
        return "done"


if __name__ == "__main__":
    question = "What is the meaning of life?"
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])

    store = Store(data={"question": question, "answer": ""}, name="hello_world")

    print(f"Question: {question}")
    flow = Flow(start=AnswerNode())
    flow.run(store)
