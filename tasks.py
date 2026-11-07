import sqlite3
from datetime import date, datetime


DB_PATH = "memory.db"


def _connect():
    return sqlite3.connect(DB_PATH)


def _init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'normal',
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def _today():
    return date.today().isoformat()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _format_task(task):
    task_id, title, due_date, priority, done, _created_at = task
    status = "done" if done else "pending"
    due_text = f", due {due_date}" if due_date else ""
    return f"{task_id}. {title}, priority {priority}, {status}{due_text}"


def _find_task(identifier):
    with _connect() as conn:
        if isinstance(identifier, int) or str(identifier).isdigit():
            task = conn.execute(
                "SELECT id, title, due_date, priority, done, created_at FROM tasks WHERE id = ?",
                (int(identifier),),
            ).fetchone()
        else:
            task = conn.execute(
                """
                SELECT id, title, due_date, priority, done, created_at
                FROM tasks
                WHERE lower(title) = lower(?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(identifier).strip(),),
            ).fetchone()

    return task


def add_task(title, due_date=None, priority="normal"):
    if not isinstance(title, str) or not title.strip():
        return "I need a task title before I can add it."

    clean_title = title.strip()
    clean_priority = (priority or "normal").strip().lower()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (title, due_date, priority, done, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (clean_title, due_date, clean_priority, _now()),
        )

    due_text = f" due on {due_date}" if due_date else ""
    return f"Task added: {clean_title}{due_text}, priority {clean_priority}. Its task number is {cursor.lastrowid}."


def list_tasks(filter="all"):
    task_filter = (filter or "all").strip().lower()
    queries = {
        "all": ("SELECT id, title, due_date, priority, done, created_at FROM tasks ORDER BY done, due_date IS NULL, due_date, created_at", ()),
        "pending": ("SELECT id, title, due_date, priority, done, created_at FROM tasks WHERE done = 0 ORDER BY due_date IS NULL, due_date, created_at", ()),
        "done": ("SELECT id, title, due_date, priority, done, created_at FROM tasks WHERE done = 1 ORDER BY created_at DESC", ()),
        "today": ("SELECT id, title, due_date, priority, done, created_at FROM tasks WHERE due_date = ? ORDER BY done, created_at", (_today(),)),
    }

    if task_filter not in queries:
        return "I can list all tasks, pending tasks, done tasks, or today's tasks."

    query, params = queries[task_filter]
    with _connect() as conn:
        tasks = conn.execute(query, params).fetchall()

    if not tasks:
        if task_filter == "all":
            return "You do not have any tasks yet."
        if task_filter == "today":
            return "You do not have any tasks due today."
        return f"You do not have any {task_filter} tasks."

    task_lines = "; ".join(_format_task(task) for task in tasks)
    return f"Here are your {task_filter} tasks: {task_lines}."


def complete_task(identifier):
    task = _find_task(identifier)
    if not task:
        return f"I could not find a task matching {identifier}."

    if task[4]:
        return f"{task[1]} is already marked done."

    with _connect() as conn:
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task[0],))

    return f"Done. I marked {task[1]} as complete."


def delete_task(identifier):
    task = _find_task(identifier)
    if not task:
        return f"I could not find a task matching {identifier}."

    with _connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task[0],))

    return f"Deleted task: {task[1]}."


def get_overdue():
    with _connect() as conn:
        tasks = conn.execute(
            """
            SELECT id, title, due_date, priority, done, created_at
            FROM tasks
            WHERE done = 0
            AND due_date IS NOT NULL
            AND due_date < ?
            ORDER BY due_date, priority, created_at
            """,
            (_today(),),
        ).fetchall()

    if not tasks:
        return "You do not have any overdue tasks."

    task_lines = "; ".join(_format_task(task) for task in tasks)
    return f"These tasks are overdue: {task_lines}."


_init_db()
