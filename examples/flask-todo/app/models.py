"""Task data-access layer over sqlite3."""
from .db import get_db


def add_task(title):
    """Insert a task; returns the new row id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO tasks (title) VALUES (?)",
        (title,),
    )
    db.commit()
    return cur.lastrowid


def get_all():
    """All tasks, newest first."""
    db = get_db()
    return db.execute(
        "SELECT id, title, done, created_at FROM tasks ORDER BY id DESC"
    ).fetchall()


def mark_done(task_id):
    """Mark a task done. Returns 'ok', 'already', or 'missing'."""
    db = get_db()
    row = db.execute("SELECT done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return "missing"
    if row["done"]:
        return "already"
    db.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    db.commit()
    return "ok"


def delete(task_id):
    """Delete a task. Returns True if a row was removed."""
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return cur.rowcount > 0
