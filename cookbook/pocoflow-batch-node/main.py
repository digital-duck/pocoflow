"""PocoFlow Batch Node — CSV chunk processing.

Demonstrates: batch-over-nodes pattern using a loop in exec().
Original PocketFlow uses BatchNode; PocoFlow loops inside exec().
"""

import os
import pandas as pd
import numpy as np
from pocoflow import Node, Flow, Store


class CSVProcessor(Node):
    """Processes a large CSV file in chunks. Replaces PocketFlow's BatchNode."""

    def __init__(self, chunk_size=1000):
        super().__init__()
        self.chunk_size = chunk_size

    def prep(self, store):
        return store["input_file"]

    def exec(self, prep_result):
        chunks = pd.read_csv(prep_result, chunksize=self.chunk_size)
        chunk_results = []
        for i, chunk in enumerate(chunks):
            result = {
                "total_sales": chunk["amount"].sum(),
                "num_transactions": len(chunk),
            }
            print(f"  Processed chunk {i + 1}: {result['num_transactions']} rows, ${result['total_sales']:,.2f}")
            chunk_results.append(result)
        return chunk_results

    def post(self, store, prep_result, exec_result):
        total_sales = sum(r["total_sales"] for r in exec_result)
        total_transactions = sum(r["num_transactions"] for r in exec_result)

        store["statistics"] = {
            "total_sales": total_sales,
            "average_sale": total_sales / total_transactions,
            "total_transactions": total_transactions,
        }
        return "show_stats"


class ShowStats(Node):
    def prep(self, store):
        return store["statistics"]

    def post(self, store, prep_result, exec_result):
        stats = prep_result
        print("\nFinal Statistics:")
        print(f"  Total Sales: ${stats['total_sales']:,.2f}")
        print(f"  Average Sale: ${stats['average_sale']:,.2f}")
        print(f"  Total Transactions: {stats['total_transactions']:,}")
        return "end"


def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("data/sales.csv"):
        print("Creating sample sales.csv...")
        np.random.seed(42)
        n_rows = 10000
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n_rows),
            "amount": np.random.normal(100, 30, n_rows).round(2),
            "product": np.random.choice(["A", "B", "C"], n_rows),
        })
        df.to_csv("data/sales.csv", index=False)

    processor = CSVProcessor(chunk_size=1000)
    show_stats = ShowStats()
    processor.then("show_stats", show_stats)

    store = Store(data={"input_file": "data/sales.csv"}, name="csv_batch")

    print("Processing sales.csv in chunks...\n")
    flow = Flow(start=processor)
    flow.run(store)


if __name__ == "__main__":
    main()
