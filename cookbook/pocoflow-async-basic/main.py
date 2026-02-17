"""PocoFlow Async Basic — async recipe finder.

Demonstrates: AsyncNode with exec_async(), multi-node wiring, retry loop.
PocoFlow's AsyncNode supports exec_async(); prep/post remain synchronous.
The framework calls asyncio.run() internally so Flow stays sync.
"""

from pocoflow import AsyncNode, Node, Flow, Store
from utils import fetch_recipes, call_llm_async


class FetchRecipesNode(AsyncNode):
    def prep(self, store):
        ingredient = input("Enter ingredient: ")
        return ingredient

    async def exec_async(self, prep_result):
        return await fetch_recipes(prep_result)

    def post(self, store, prep_result, exec_result):
        store["recipes"] = exec_result
        store["ingredient"] = prep_result
        return "suggest"


class SuggestRecipeNode(AsyncNode):
    def prep(self, store):
        return store["recipes"]

    async def exec_async(self, prep_result):
        return await call_llm_async(
            f"Choose best recipe from: {', '.join(prep_result)}"
        )

    def post(self, store, prep_result, exec_result):
        store["suggestion"] = exec_result
        return "approve"


class GetApprovalNode(Node):
    def prep(self, store):
        return store["suggestion"]

    def exec(self, prep_result):
        return input(f"\nAccept this recipe? (y/n): ").lower()

    def post(self, store, prep_result, exec_result):
        if exec_result == "y":
            print(f"\nGreat choice! Recipe: {store['suggestion']}")
            print(f"Ingredient: {store['ingredient']}")
            return "accept"
        print("\nLet's try another recipe...")
        return "retry"


if __name__ == "__main__":
    fetch = FetchRecipesNode()
    suggest = SuggestRecipeNode()
    approve = GetApprovalNode()

    fetch.then("suggest", suggest)
    suggest.then("approve", approve)
    approve.then("retry", suggest)   # loop back
    # "accept" has no successor → flow ends

    store = Store(
        data={"recipes": [], "ingredient": "", "suggestion": ""},
        name="recipe_finder",
    )

    print("\nWelcome to Recipe Finder!")
    print("------------------------")
    flow = Flow(start=fetch)
    flow.run(store)
    print("\nThanks for using Recipe Finder!")
