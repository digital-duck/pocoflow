"""PocoFlow MCP — Model Context Protocol tool calling."""

import click
import yaml
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


# ─── Local tool implementations (no MCP server needed) ───────────────
TOOLS = {
    "add": {"description": "Add two numbers", "params": ["a", "b"],
            "fn": lambda a, b: a + b},
    "subtract": {"description": "Subtract b from a", "params": ["a", "b"],
                 "fn": lambda a, b: a - b},
    "multiply": {"description": "Multiply two numbers", "params": ["a", "b"],
                 "fn": lambda a, b: a * b},
    "divide": {"description": "Divide a by b", "params": ["a", "b"],
               "fn": lambda a, b: a / b if b != 0 else "Error: division by zero"},
}


def format_tool_info():
    lines = []
    for i, (name, info) in enumerate(TOOLS.items(), 1):
        params = ", ".join(f"{p} (int)" for p in info["params"])
        lines.append(f"[{i}] {name}\n  Description: {info['description']}\n  Parameters: {params}")
    return "\n".join(lines)


class GetToolsNode(Node):
    def exec(self, prep_result):
        return format_tool_info()

    def post(self, store, prep_result, exec_result):
        store["tool_info"] = exec_result
        print("Available tools loaded.")
        return "decide"


class DecideToolNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        tool_info = store["tool_info"]
        question = store["question"]
        llm = store["_llm"]
        model = store.get("_model")

        prompt = f"""### CONTEXT
You are an assistant that can use tools.

### ACTION SPACE
{tool_info}

### TASK
Answer this question: "{question}"

Analyze the question, extract numbers, and decide which tool to use.
Return in this format:

```yaml
thinking: |
    <reasoning>
tool: <tool name>
parameters:
    a: <value>
    b: <value>
```"""
        return prompt, llm, model

    def exec(self, prep_result):
        prompt, llm, model = prep_result
        print("Analyzing question...")
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        try:
            yaml_str = exec_result.split("```yaml")[1].split("```")[0].strip()
            decision = yaml.safe_load(yaml_str)
            store["tool_name"] = decision["tool"]
            store["parameters"] = decision["parameters"]
            print(f"  Selected tool: {decision['tool']}")
            print(f"  Parameters: {decision['parameters']}")
            return "execute"
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return None


class ExecuteToolNode(Node):
    def prep(self, store):
        return store["tool_name"], store["parameters"]

    def exec(self, prep_result):
        tool_name, parameters = prep_result
        print(f"  Executing '{tool_name}' with {parameters}")
        tool = TOOLS.get(tool_name)
        if not tool:
            return f"Unknown tool: {tool_name}"
        try:
            result = tool["fn"](**{k: int(v) for k, v in parameters.items()})
            return result
        except Exception as e:
            return f"Error: {e}"

    def post(self, store, prep_result, exec_result):
        print(f"\n  Result: {exec_result}")
        store["result"] = exec_result
        return "done"


@click.command()
@click.argument("question", default="What is 982713504867129384651 plus 73916582047365810293746529?")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
def main(question, provider, model):
    """Use LLM to select and call math tools via MCP pattern."""
    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    get_tools = GetToolsNode()
    decide = DecideToolNode()
    execute = ExecuteToolNode()

    get_tools.then("decide", decide)
    decide.then("execute", execute)

    store = Store(
        data={"question": question, "_llm": llm, "_model": model},
        name="mcp",
    )

    print(f"Processing: {question}")
    flow = Flow(start=get_tools)
    flow.run(store)


if __name__ == "__main__":
    main()
