"""PicoFlow — minimal hello-world example.

Run:
    python examples/hello.py
"""

from picoflow import Node, Flow, Store


class GreetNode(Node):
    def prep(self, store):
        return store["name"]

    def exec(self, name):
        return f"Hello, {name}!"

    def post(self, store, prep, greeting):
        store["greeting"] = greeting
        return "done"


class ShoutNode(Node):
    def prep(self, store):
        return store["greeting"]

    def exec(self, greeting):
        return greeting.upper()

    def post(self, store, prep, shouted):
        store["shouted"] = shouted
        return "done"


if __name__ == "__main__":
    greet = GreetNode()
    shout = ShoutNode()
    greet.then("done", shout)

    store = Store(
        data={"name": "PicoFlow", "greeting": "", "shouted": ""},
        schema={"name": str},
        name="hello_demo",
    )

    flow = Flow(start=greet)
    flow.on("node_end", lambda name, action, elapsed, s:
        print(f"  ✓ {name} → '{action}'  ({elapsed*1000:.1f}ms)"))

    print("Running hello flow...")
    flow.run(store)
    print(f"greeting : {store['greeting']}")
    print(f"shouted  : {store['shouted']}")
