"""PocoFlow Text-to-SQL — natural language to SQL with debug loop.

Demonstrates: schema retrieval, LLM SQL generation, execution, debug loop.
"""

import os
import click
from pocoflow import Flow, Store
from pocoflow.utils import UniversalLLMProvider
from nodes import GetSchema, GenerateSQL, ExecuteSQL, DebugSQL
from populate_db import populate_database, DB_FILE


@click.command()
@click.argument("query", default="total products per category")
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
@click.option("--db", default=DB_FILE, help="Path to SQLite database")
@click.option("--max-retries", default=3, help="Max debug retries on SQL error")
def main(query, provider, model, db, max_retries):
    """Convert a natural language query to SQL and execute it."""
    # Auto-populate DB if missing
    if not os.path.exists(db) or os.path.getsize(db) == 0:
        print(f"Database at {db} missing or empty. Populating...")
        populate_database(db)

    llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])

    # Build flow: GetSchema -> GenerateSQL -> ExecuteSQL (with debug loop)
    get_schema = GetSchema()
    generate_sql = GenerateSQL()
    execute_sql = ExecuteSQL()
    debug_sql = DebugSQL()

    get_schema.then("default", generate_sql)
    generate_sql.then("default", execute_sql)
    execute_sql.then("error_retry", debug_sql)
    debug_sql.then("default", execute_sql)

    store = Store(
        data={
            "db_path": db,
            "natural_query": query,
            "max_debug_attempts": max_retries,
            "debug_attempts": 0,
            "final_result": None,
            "final_error": None,
            "_llm": llm,
            "_model": model,
        },
        name="text2sql",
    )

    print(f"\n=== Starting Text-to-SQL Workflow ===")
    print(f"Query: '{query}'")
    print(f"Database: {db}")
    print(f"Max Debug Retries on SQL Error: {max_retries}")
    print("=" * 45)

    flow = Flow(start=get_schema)
    flow.run(store)

    if store.get("final_error"):
        print("\n=== Workflow Completed with Error ===")
        print(f"Error: {store['final_error']}")
    elif store.get("final_result") is not None:
        print("\n=== Workflow Completed Successfully ===")
    else:
        print("\n=== Workflow Completed (Unknown State) ===")

    print("=" * 36)


if __name__ == "__main__":
    main()
