"""Text-to-SQL nodes: schema retrieval, SQL generation, execution, and debug loop."""

import sqlite3
import time
import yaml
from pocoflow import Node


def _llm_call(llm, model, prompt):
    """Helper: call LLM and return content or raise on failure."""
    response = llm.call(prompt, model=model)
    if not response.success:
        raise RuntimeError(f"LLM failed: {response.error_history}")
    return response.content


class GetSchema(Node):
    """Connects to the SQLite database and extracts the schema."""

    def prep(self, store):
        return store["db_path"]

    def exec(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        schema = []
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            schema.append(f"Table: {table_name}")
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for col in columns:
                schema.append(f"  - {col[1]} ({col[2]})")
            schema.append("")
        conn.close()
        return "\n".join(schema).strip()

    def post(self, store, prep_result, exec_result):
        store["schema"] = exec_result
        print("\n===== DB SCHEMA =====\n")
        print(exec_result)
        print("\n=====================\n")
        return "default"


class GenerateSQL(Node):
    """Uses the LLM to translate a natural language query into SQL."""

    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return {
            "natural_query": store["natural_query"],
            "schema": store["schema"],
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        natural_query = prep_result["natural_query"]
        schema = prep_result["schema"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        prompt = f"""Given SQLite schema:
{schema}

Question: "{natural_query}"

Respond ONLY with a YAML block containing the SQL query under the key 'sql':
```yaml
sql: |
  SELECT ...
```"""
        response = _llm_call(llm, model, prompt)
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        structured_result = yaml.safe_load(yaml_str)
        sql_query = structured_result["sql"].strip().rstrip(";")
        return sql_query

    def post(self, store, prep_result, exec_result):
        store["generated_sql"] = exec_result
        store["debug_attempts"] = 0
        print(f"\n===== GENERATED SQL =====\n")
        print(exec_result)
        print("\n=========================\n")
        return "default"


class ExecuteSQL(Node):
    """Executes the generated SQL against the database.

    Returns:
        None on success (flow ends) or when max retries reached.
        "error_retry" on failure to trigger DebugSQL.
    """

    def prep(self, store):
        return {
            "db_path": store["db_path"],
            "generated_sql": store["generated_sql"],
        }

    def exec(self, prep_result):
        db_path = prep_result["db_path"]
        sql_query = prep_result["generated_sql"]
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            start_time = time.time()
            cursor.execute(sql_query)

            is_select = sql_query.strip().upper().startswith(("SELECT", "WITH"))
            if is_select:
                results = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description] if cursor.description else []
            else:
                conn.commit()
                results = f"Query OK. Rows affected: {cursor.rowcount}"
                column_names = []
            conn.close()
            duration = time.time() - start_time
            print(f"SQL executed in {duration:.3f} seconds.")
            return (True, results, column_names)
        except sqlite3.Error as e:
            print(f"SQLite Error during execution: {e}")
            if "conn" in locals() and conn:
                try:
                    conn.close()
                except Exception:
                    pass
            return (False, str(e), [])

    def post(self, store, prep_result, exec_result):
        success, result_or_error, column_names = exec_result

        if success:
            store["final_result"] = result_or_error
            store["result_columns"] = column_names
            print("\n===== SQL EXECUTION SUCCESS =====\n")
            if isinstance(result_or_error, list):
                if column_names:
                    print(" | ".join(column_names))
                    print("-" * (sum(len(str(c)) for c in column_names) + 3 * (len(column_names) - 1)))
                if not result_or_error:
                    print("(No results found)")
                else:
                    for row in result_or_error:
                        print(" | ".join(map(str, row)))
            else:
                print(result_or_error)
            print("\n=================================\n")
            return None  # Flow ends on success

        # Execution failed
        store["execution_error"] = result_or_error
        store["debug_attempts"] = store.get("debug_attempts", 0) + 1
        max_attempts = store.get("max_debug_attempts", 3)

        print(f"\n===== SQL EXECUTION FAILED (Attempt {store['debug_attempts']}) =====\n")
        print(f"Error: {store['execution_error']}")
        print("\n=========================================\n")

        if store["debug_attempts"] >= max_attempts:
            print(f"Max debug attempts ({max_attempts}) reached. Stopping.")
            store["final_error"] = (
                f"Failed to execute SQL after {max_attempts} attempts. "
                f"Last error: {store['execution_error']}"
            )
            return None  # Flow ends after max retries

        print("Attempting to debug the SQL...")
        return "error_retry"


class DebugSQL(Node):
    """Uses the LLM to fix a failed SQL query based on the error message."""

    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return {
            "natural_query": store.get("natural_query"),
            "schema": store.get("schema"),
            "generated_sql": store.get("generated_sql"),
            "execution_error": store.get("execution_error"),
            "llm": store["_llm"],
            "model": store.get("_model"),
        }

    def exec(self, prep_result):
        natural_query = prep_result["natural_query"]
        schema = prep_result["schema"]
        failed_sql = prep_result["generated_sql"]
        error_message = prep_result["execution_error"]
        llm = prep_result["llm"]
        model = prep_result["model"]

        prompt = f"""The following SQLite SQL query failed:
```sql
{failed_sql}
```
It was generated for: "{natural_query}"
Schema:
{schema}
Error: "{error_message}"

Provide a corrected SQLite query.

Respond ONLY with a YAML block containing the corrected SQL under the key 'sql':
```yaml
sql: |
  SELECT ... -- corrected query
```"""
        response = _llm_call(llm, model, prompt)
        yaml_str = response.split("```yaml")[1].split("```")[0].strip()
        structured_result = yaml.safe_load(yaml_str)
        corrected_sql = structured_result["sql"].strip().rstrip(";")
        return corrected_sql

    def post(self, store, prep_result, exec_result):
        store["generated_sql"] = exec_result
        store.pop("execution_error", None)

        print(f"\n===== REVISED SQL (Attempt {store.get('debug_attempts', 0) + 1}) =====\n")
        print(exec_result)
        print("\n====================================\n")
        return "default"
