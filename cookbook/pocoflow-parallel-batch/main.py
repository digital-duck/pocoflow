"""PocoFlow Parallel Batch — sequential vs parallel async processing.

Demonstrates: AsyncNode, asyncio.gather for parallelism.
Original PocketFlow uses AsyncBatchNode / AsyncParallelBatchNode;
PocoFlow uses AsyncNode with loop (sequential) vs asyncio.gather (parallel).
"""

import asyncio
import time
from pocoflow import AsyncNode, Flow, Store


async def dummy_llm_summarize(text: str) -> str:
    """Simulates an async LLM call that takes 1 second."""
    await asyncio.sleep(1)
    return f"Summarized({len(text)} chars)"


class SequentialSummarize(AsyncNode):
    """Processes items sequentially — one at a time."""

    def prep(self, store):
        return list(store["data"].items())

    async def exec_async(self, prep_result):
        results = []
        for filename, content in prep_result:
            print(f"  [Sequential] Summarizing {filename}...")
            summary = await dummy_llm_summarize(content)
            results.append((filename, summary))
        return results

    def post(self, store, prep_result, exec_result):
        store["sequential_summaries"] = dict(exec_result)
        return "done"


class ParallelSummarize(AsyncNode):
    """Processes items in parallel using asyncio.gather."""

    def prep(self, store):
        return list(store["data"].items())

    async def exec_async(self, prep_result):
        async def process_one(filename, content):
            print(f"  [Parallel] Summarizing {filename}...")
            summary = await dummy_llm_summarize(content)
            return (filename, summary)

        tasks = [process_one(f, c) for f, c in prep_result]
        return await asyncio.gather(*tasks)

    def post(self, store, prep_result, exec_result):
        store["parallel_summaries"] = dict(exec_result)
        return "done"


def main():
    data = {
        "file1.txt": "Hello world 1",
        "file2.txt": "Hello world 2",
        "file3.txt": "Hello world 3",
    }

    # Sequential run
    store_seq = Store(data={"data": data}, name="sequential")
    print("\n=== Running Sequential ===")
    t0 = time.time()
    Flow(start=SequentialSummarize()).run(store_seq)
    t1 = time.time()

    # Parallel run
    store_par = Store(data={"data": data}, name="parallel")
    print("\n=== Running Parallel ===")
    t2 = time.time()
    Flow(start=ParallelSummarize()).run(store_par)
    t3 = time.time()

    print("\n--- Results ---")
    print(f"Sequential Summaries: {store_seq['sequential_summaries']}")
    print(f"Parallel Summaries:   {store_par['parallel_summaries']}")
    print(f"Sequential took: {t1 - t0:.2f} seconds")
    print(f"Parallel took:   {t3 - t2:.2f} seconds")


if __name__ == "__main__":
    main()
