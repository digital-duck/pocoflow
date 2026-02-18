"""PocoFlow TAO — Think-Action-Observe reasoning loop."""

import click
import yaml
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


class ThinkNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        query = store.get("query", "")
        observations = store.get("observations", [])
        thought_num = store.get("current_thought_number", 0) + 1
        store["current_thought_number"] = thought_num

        obs_text = "\n".join(
            [f"Observation {i+1}: {obs}" for i, obs in enumerate(observations)]
        ) or "No observations yet."

        return {
            "query": query,
            "observations_text": obs_text,
            "thought_num": thought_num,
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        query = prep_result["query"]
        obs_text = prep_result["observations_text"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        prompt = f"""You are an AI assistant solving a problem. Based on the user's query and previous observations, think about what action to take next.

User query: {query}

Previous observations:
{obs_text}

Return your thinking and decision in YAML format:
```yaml
thinking: |
    <detailed thinking process>
action: <action name: 'search', 'calculate', or 'answer'>
action_input: <input for the action>
is_final: <true if this is the final answer, false otherwise>
```"""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")

        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        thought = yaml.safe_load(yaml_str)
        thought["thought_number"] = prep_result["thought_num"]
        return thought

    def post(self, store, prep_result, exec_result):
        store.setdefault("thoughts", []).append(exec_result)
        store["current_action"] = exec_result["action"]
        store["current_action_input"] = exec_result["action_input"]

        if exec_result.get("is_final", False):
            store["final_answer"] = exec_result["action_input"]
            print(f"  Final Answer: {exec_result['action_input']}")
            return "end"

        print(f"  Thought {exec_result['thought_number']}: execute {exec_result['action']}")
        return "action"


class ActionNode(Node):
    def prep(self, store):
        return store["current_action"], store["current_action_input"]

    def exec(self, prep_result):
        action, action_input = prep_result
        print(f"  Executing: {action}({action_input})")

        if action == "search":
            return f"Search results: Information about '{action_input}'..."
        elif action == "calculate":
            try:
                return f"Calculation result: {eval(str(action_input))}"
            except Exception:
                return f"Unable to calculate: {action_input}"
        elif action == "answer":
            return action_input
        return f"Unknown action: {action}"

    def post(self, store, prep_result, exec_result):
        store["current_action_result"] = exec_result
        return "observe"


class ObserveNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return {
            "action": store["current_action"],
            "action_input": store["current_action_input"],
            "action_result": store["current_action_result"],
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        llm = prep_result["llm"]
        model = prep_result["model"]
        prompt = f"""You are an observer. Analyze this action result and provide a concise observation.

Action: {prep_result['action']}
Input: {prep_result['action_input']}
Result: {prep_result['action_result']}

Describe what you see objectively. Don't make decisions."""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        observation = response.content
        print(f"  Observation: {observation[:80]}...")
        return observation

    def post(self, store, prep_result, exec_result):
        store.setdefault("observations", []).append(exec_result)
        return "think"


class EndNode(Node):
    def exec(self, prep_result):
        print("Flow ended.")
        return "done"


@click.command()
@click.argument("query", default="I need to understand the latest developments in artificial intelligence")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(query, provider, model):
    """Run a Think-Action-Observe reasoning loop."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    think = ThinkNode()
    action = ActionNode()
    observe = ObserveNode()
    end = EndNode()

    think.then("action", action)
    think.then("end", end)
    action.then("observe", observe)
    observe.then("think", think)

    store = Store(
        data={
            "query": query,
            "thoughts": [],
            "observations": [],
            "current_thought_number": 0,
            "_llm": llm,
            "_model": model,
        },
        name="tao",
    )

    flow = Flow(start=think)
    flow.run(store)

    if "final_answer" in store:
        print(f"\nFinal Answer:\n{store['final_answer']}")


if __name__ == "__main__":
    main()
