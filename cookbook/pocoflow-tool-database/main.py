"""PocoFlow Tool Database — SQLite database operations via flow."""

import os
import sqlite3

import click
from pocoflow import Node, Flow, Store


DB_PATH = os.path.join(os.path.dirname(__file__), "tasks.db")


def execute_sql(query, params=None, db_path=DB_PATH):
    """Execute a SQL query and return results."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        result = cursor.fetchall()
        conn.commit()
        return result
    finally:
        conn.close()


class InitDatabaseNode(Node):
    def exec(self, prep_result):
        execute_sql("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        return "Database initialized"

    def post(self, store, prep_result, exec_result):
        store["db_status"] = exec_result
        print(f"  {exec_result}")
        return "create"


class CreateTaskNode(Node):
    def prep(self, store):
        return store.get("task_title", ""), store.get("task_description", "")

    def exec(self, prep_result):
        title, description = prep_result
        execute_sql(
            "INSERT INTO tasks (title, description) VALUES (?, ?)",
            (title, description),
        )
        return f"Task '{title}' created"

    def post(self, store, prep_result, exec_result):
        store["task_status"] = exec_result
        print(f"  {exec_result}")
        return "list"


class ListTasksNode(Node):
    def exec(self, prep_result):
        return execute_sql("SELECT * FROM tasks")

    def post(self, store, prep_result, exec_result):
        store["tasks"] = exec_result
        return "done"


@click.command()
@click.option("--title", default="Example Task", help="Task title")
@click.option("--description", default="Created via PocoFlow", help="Task description")
def main(title, description):
    """Run database operations: init, create task, list tasks."""
    init_db = InitDatabaseNode()
    create_task = CreateTaskNode()
    list_tasks = ListTasksNode()

    init_db.then("create", create_task)
    create_task.then("list", list_tasks)

    store = Store(
        data={"task_title": title, "task_description": description},
        name="tool_database",
    )

    flow = Flow(start=init_db)
    flow.run(store)

    print(f"\nDatabase Status: {store.get('db_status')}")
    print(f"Task Status: {store.get('task_status')}")
    print("\nAll Tasks:")
    for task in store.get("tasks", []):
        print(f"  ID: {task[0]} | Title: {task[1]} | Desc: {task[2]} | Status: {task[3]} | Created: {task[4]}")


if __name__ == "__main__":
    main()
