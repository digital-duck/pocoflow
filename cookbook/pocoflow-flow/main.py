"""PocoFlow Flow — multi-node text converter with action routing.

Demonstrates: multiple nodes, .then() wiring, action-based branching, self-loops.
No LLM needed — pure framework exercise.
"""

from pocoflow import Node, Flow, Store


class TextInputNode(Node):
    def prep(self, store):
        if "text" not in store.as_dict() or not store["text"]:
            text = input("\nEnter text to convert: ")
            store["text"] = text
        return store["text"]

    def exec(self, prep_result):
        return prep_result  # pass-through

    def post(self, store, prep_result, exec_result):
        print("\nChoose transformation:")
        print("1. Convert to UPPERCASE")
        print("2. Convert to lowercase")
        print("3. Reverse text")
        print("4. Remove extra spaces")
        print("5. Exit")

        choice = input("\nYour choice (1-5): ")

        if choice == "5":
            return "exit"

        store["choice"] = choice
        return "transform"


class TextTransformNode(Node):
    def prep(self, store):
        return store["text"], store["choice"]

    def exec(self, prep_result):
        text, choice = prep_result
        if choice == "1":
            return text.upper()
        elif choice == "2":
            return text.lower()
        elif choice == "3":
            return text[::-1]
        elif choice == "4":
            return " ".join(text.split())
        return "Invalid option!"

    def post(self, store, prep_result, exec_result):
        print(f"\nResult: {exec_result}")

        if input("\nConvert another text? (y/n): ").lower() == "y":
            store["text"] = ""  # clear for new input
            return "input"
        return "exit"


if __name__ == "__main__":
    print("\nWelcome to Text Converter!")
    print("=========================")

    text_input = TextInputNode()
    text_transform = TextTransformNode()

    text_input.then("transform", text_transform)
    text_transform.then("input", text_input)
    # "exit" has no successor → flow terminates

    store = Store(data={"text": "", "choice": ""}, name="text_converter")
    flow = Flow(start=text_input)
    flow.run(store)

    print("\nThank you for using Text Converter!")
