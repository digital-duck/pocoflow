"""PocoFlow Workflow — article writing pipeline.

Demonstrates: multi-step workflow, YAML structured output, batch-in-exec pattern.
Original PocketFlow uses BatchNode; here we loop inside exec().
"""

import sys
from pocoflow import Flow, Store
from nodes import GenerateOutline, WriteSections, ApplyStyle


def main():
    topic = "AI Safety"
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])

    outline = GenerateOutline()
    write = WriteSections()
    style = ApplyStyle()

    outline.then("default", write)
    write.then("default", style)
    # style returns "default" with no successor -> flow ends

    store = Store(
        data={"topic": topic, "sections": [], "draft": "", "final_article": ""},
        name="article_workflow",
    )

    print(f"\n=== Starting Article Workflow on Topic: {topic} ===\n")
    flow = Flow(start=outline)
    flow.run(store)

    print("\n=== Workflow Completed ===\n")
    print(f"Topic: {store['topic']}")
    print(f"Draft Length: {len(store['draft'])} characters")
    print(f"Final Article Length: {len(store['final_article'])} characters")


if __name__ == "__main__":
    main()
