"""PocoFlow Communication — inter-node communication via shared Store."""

import click
from pocoflow import Node, Flow, Store


class TextInputNode(Node):
    def prep(self, store):
        return input("Enter text (or 'q' to quit): ")

    def exec(self, prep_result):
        return prep_result

    def post(self, store, prep_result, exec_result):
        if exec_result.strip().lower() == "q":
            return "exit"
        store["text"] = exec_result
        if "stats" not in store:
            store["stats"] = {"total_texts": 0, "total_words": 0}
        store["stats"]["total_texts"] += 1
        return "count"


class WordCounterNode(Node):
    def prep(self, store):
        return store["text"]

    def exec(self, prep_result):
        return len(prep_result.split())

    def post(self, store, prep_result, exec_result):
        store["stats"]["total_words"] += exec_result
        return "show"


class ShowStatsNode(Node):
    def prep(self, store):
        return store["stats"]

    def exec(self, prep_result):
        return prep_result

    def post(self, store, prep_result, exec_result):
        stats = exec_result
        print(f"\nStatistics:")
        print(f"- Texts processed: {stats['total_texts']}")
        print(f"- Total words: {stats['total_words']}")
        avg = stats["total_words"] / stats["total_texts"]
        print(f"- Average words per text: {avg:.1f}\n")
        return "continue"


class EndNode(Node):
    def exec(self, prep_result):
        print("\nGoodbye!")
        return "done"


@click.command()
def main():
    """Interactive word-counter showing inter-node communication via Store."""
    text_input = TextInputNode()
    word_counter = WordCounterNode()
    show_stats = ShowStatsNode()
    end_node = EndNode()

    text_input.then("count", word_counter)
    text_input.then("exit", end_node)
    word_counter.then("show", show_stats)
    show_stats.then("continue", text_input)

    store = Store(data={}, name="communication")
    flow = Flow(start=text_input)
    flow.run(store)


if __name__ == "__main__":
    main()
