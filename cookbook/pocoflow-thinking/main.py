"""PocoFlow Thinking -- chain-of-thought reasoning with a self-looping node.

The LLM iteratively builds and refines a structured plan using YAML output.
Each iteration evaluates the previous thought, executes the next pending step,
and updates the plan until the problem is solved.
"""

import textwrap
import yaml
import click
from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider


# ---------------------------------------------------------------------------
# Helper: pretty-print a plan list
# ---------------------------------------------------------------------------

def format_plan(plan_items, indent_level=0):
    """Recursively format a structured plan list for display."""
    indent = "  " * indent_level
    output = []

    if isinstance(plan_items, list):
        for item in plan_items:
            if isinstance(item, dict):
                status = item.get("status", "Unknown")
                desc = item.get("description", "No description")
                result = item.get("result", "")
                mark = item.get("mark", "")

                line = f"{indent}- [{status}] {desc}"
                if result:
                    line += f": {result}"
                if mark:
                    line += f" ({mark})"
                output.append(line)

                sub_steps = item.get("sub_steps")
                if sub_steps:
                    output.append(format_plan(sub_steps, indent_level + 1))
            elif isinstance(item, str):
                output.append(f"{indent}- {item}")
            else:
                output.append(f"{indent}- {str(item)}")
    elif isinstance(plan_items, str):
        output.append(f"{indent}{plan_items}")
    else:
        output.append(f"{indent}# Invalid plan format: {type(plan_items)}")

    return "\n".join(output)


def _format_plan_for_prompt(plan_items, indent_level=0):
    """Simplified plan formatting used inside the LLM prompt."""
    indent = "  " * indent_level
    output = []

    if isinstance(plan_items, list):
        for item in plan_items:
            if isinstance(item, dict):
                status = item.get("status", "Unknown")
                desc = item.get("description", "No description")
                output.append(f"{indent}- [{status}] {desc}")
                sub_steps = item.get("sub_steps")
                if sub_steps:
                    output.append(
                        _format_plan_for_prompt(sub_steps, indent_level + 1)
                    )
            else:
                output.append(f"{indent}- {str(item)}")
    else:
        output.append(f"{indent}{str(plan_items)}")

    return "\n".join(output)


# ---------------------------------------------------------------------------
# Chain-of-Thought Node
# ---------------------------------------------------------------------------

class ChainOfThoughtNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        question = store.get("question", "")
        thoughts = store.get("thoughts", [])
        current_thought_number = store.get("current_thought_number", 0)

        # Increment for this iteration
        store["current_thought_number"] = current_thought_number + 1

        # Build text summary of previous thoughts and extract last plan
        last_plan_structure = None
        if thoughts:
            thought_blocks = []
            for i, t in enumerate(thoughts):
                block = f"Thought {t.get('thought_number', i + 1)}:\n"
                thinking = textwrap.dedent(
                    t.get("current_thinking", "N/A")
                ).strip()
                block += f"  Thinking:\n{textwrap.indent(thinking, '    ')}\n"

                plan_list = t.get("planning", [])
                plan_str = format_plan(plan_list, indent_level=2)
                block += (
                    f"  Plan Status After Thought "
                    f"{t.get('thought_number', i + 1)}:\n{plan_str}"
                )

                if i == len(thoughts) - 1:
                    last_plan_structure = plan_list

                thought_blocks.append(block)

            thoughts_text = "\n--------------------\n".join(thought_blocks)
        else:
            thoughts_text = "No previous thoughts yet."
            last_plan_structure = [
                {"description": "Understand the problem", "status": "Pending"},
                {"description": "Develop a high-level plan", "status": "Pending"},
                {"description": "Conclusion", "status": "Pending"},
            ]

        last_plan_text = (
            _format_plan_for_prompt(last_plan_structure)
            if last_plan_structure
            else "# No previous plan available."
        )

        return {
            "question": question,
            "thoughts_text": thoughts_text,
            "last_plan_text": last_plan_text,
            "current_thought_number": current_thought_number + 1,
            "is_first_thought": not thoughts,
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        question = prep_result["question"]
        thoughts_text = prep_result["thoughts_text"]
        last_plan_text = prep_result["last_plan_text"]
        current_thought_number = prep_result["current_thought_number"]
        is_first_thought = prep_result["is_first_thought"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        # -- Build the prompt ------------------------------------------------
        instruction_base = textwrap.dedent(f"""\
            Your task is to generate the next thought (Thought {current_thought_number}).

            Instructions:
            1.  **Evaluate Previous Thought:** If not the first thought, start
                `current_thinking` by evaluating Thought {current_thought_number - 1}.
                State: "Evaluation of Thought {current_thought_number - 1}:
                [Correct/Minor Issues/Major Error - explain]". Address errors first.
            2.  **Execute Step:** Execute the first step in the plan with
                `status: Pending`.
            3.  **Maintain Plan (Structure):** Generate an updated `planning` list.
                Each item is a dict with keys: `description` (string), `status`
                (string: "Pending", "Done", "Verification Needed"), and optionally
                `result` (string, concise summary when Done) or `mark` (string,
                reason for Verification Needed). Sub-steps use a `sub_steps` key
                containing a list of these dicts.
            4.  **Update Current Step Status:** Change the executed step's `status`
                to "Done" and add a `result` key with a concise summary.
            5.  **Refine Plan (Sub-steps):** If a "Pending" step is complex, add
                `sub_steps` to break it down. Keep the parent "Pending" until all
                sub-steps are "Done".
            6.  **Refine Plan (Errors):** Modify the plan logically based on
                evaluation findings.
            7.  **Final Step:** Ensure the plan has a final step dict like
                {{'description': "Conclusion", 'status': "Pending"}}.
            8.  **Termination:** Set `next_thought_needed` to `false` ONLY when
                executing the step with `description: "Conclusion"`.
        """)

        if is_first_thought:
            instruction_context = textwrap.dedent("""\
                **This is the first thought:** Create an initial plan as a list of
                dicts (keys: description, status). Include sub-steps via the
                `sub_steps` key if needed. Then execute the first step in
                `current_thinking` and provide the updated plan (marking step 1
                `status: Done` with a `result`).
            """)
        else:
            instruction_context = textwrap.dedent(f"""\
                **Previous Plan (Simplified View):**
                {last_plan_text}

                Start `current_thinking` by evaluating Thought \
{current_thought_number - 1}. Then proceed with the first step where
                `status: Pending`. Update the plan structure reflecting evaluation,
                execution, and refinements.
            """)

        instruction_format = textwrap.dedent("""\
            Format your response ONLY as a YAML structure enclosed in ```yaml ... ```:
            ```yaml
            current_thinking: |
              # Evaluation of Thought N: [Assessment] ... (if applicable)
              # Thinking for the current step...
            planning:
              - description: "Step 1"
                status: "Done"
                result: "Concise result summary"
              - description: "Step 2 Complex Task"
                status: "Pending"
                sub_steps:
                  - description: "Sub-task 2a"
                    status: "Pending"
                  - description: "Sub-task 2b"
                    status: "Verification Needed"
                    mark: "Result from Thought X seems off"
              - description: "Conclusion"
                status: "Pending"
            next_thought_needed: true
            ```
        """)

        prompt = textwrap.dedent(f"""\
            You are a meticulous AI assistant solving a complex problem step-by-step
            using a structured plan. You critically evaluate previous steps, refine
            the plan with sub-steps if needed, and handle errors logically. Use the
            specified YAML dictionary structure for the plan.

            Problem: {question}

            Previous thoughts:
            {thoughts_text}
            --------------------
            {instruction_base}
            {instruction_context}
            {instruction_format}
        """)

        # -- Call LLM --------------------------------------------------------
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")

        # -- Parse YAML ------------------------------------------------------
        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        thought_data = yaml.safe_load(yaml_str)

        # -- Validate --------------------------------------------------------
        assert thought_data is not None, "YAML parsing failed, result is None"
        assert "current_thinking" in thought_data, (
            "LLM response missing 'current_thinking'"
        )
        assert "next_thought_needed" in thought_data, (
            "LLM response missing 'next_thought_needed'"
        )
        assert "planning" in thought_data, "LLM response missing 'planning'"
        assert isinstance(thought_data.get("planning"), list), (
            "'planning' is not a list"
        )

        thought_data["thought_number"] = current_thought_number
        return thought_data

    def post(self, store, prep_result, exec_result):
        # Append thought to running list
        if "thoughts" not in store:
            store["thoughts"] = []
        store["thoughts"].append(exec_result)

        plan_list = exec_result.get("planning", ["Error: Planning data missing."])
        plan_str = format_plan(plan_list, indent_level=1)

        thought_num = exec_result.get("thought_number", "N/A")
        current_thinking = exec_result.get(
            "current_thinking", "Error: Missing thinking content."
        )
        dedented_thinking = textwrap.dedent(current_thinking).strip()

        # Check termination
        if not exec_result.get("next_thought_needed", True):
            store["solution"] = dedented_thinking
            print(f"\nThought {thought_num} (Conclusion):")
            print(textwrap.indent(dedented_thinking, "  "))
            print("\nFinal Plan Status:")
            print(textwrap.indent(plan_str, "  "))
            print("\n=== FINAL SOLUTION ===")
            print(dedented_thinking)
            print("======================\n")
            return "end"

        # Otherwise keep iterating
        print(f"\nThought {thought_num}:")
        print(textwrap.indent(dedented_thinking, "  "))
        print("\nCurrent Plan Status:")
        print(textwrap.indent(plan_str, "  "))
        print("-" * 50)

        return "continue"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

DEFAULT_QUESTION = (
    "You keep rolling a fair die until you roll three, four, five in that "
    "order consecutively on three rolls. What is the probability that you "
    "roll the die an odd number of times?"
)


@click.command()
@click.option(
    "--provider",
    default="anthropic",
    help="LLM provider (openai, anthropic, gemini, openrouter, ollama)",
)
@click.option(
    "--model",
    default=None,
    help="Model name (provider default if omitted)",
)
@click.argument("question", default=DEFAULT_QUESTION)
def main(provider, model, question):
    """Chain-of-thought reasoning with iterative plan refinement."""
    print(f"=== PocoFlow Thinking ===\n")
    print(f"Question: {question}\n")

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    cot = ChainOfThoughtNode()
    cot.then("continue", cot)  # self-loop

    store = Store(
        data={
            "question": question,
            "thoughts": [],
            "current_thought_number": 0,
            "solution": None,
            "_llm": llm,
            "_model": model,
        },
        name="thinking",
    )

    flow = Flow(start=cot)
    flow.run(store)

    if store.get("solution"):
        print("Done. Solution stored in store['solution'].")


if __name__ == "__main__":
    main()
