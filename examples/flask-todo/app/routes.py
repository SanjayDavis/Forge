"""HTTP routes: list, add, complete, delete."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from .models import add_task, delete, get_all, mark_done

bp = Blueprint("tasks", __name__)


@bp.get("/")
def index():
    return render_template("index.html", tasks=get_all())


@bp.post("/add")
def add():
    title = request.form.get("title", "").strip()
    if title:
        add_task(title)
    return redirect(url_for("tasks.index"))


@bp.post("/done/<int:task_id>")
def done(task_id):
    result = mark_done(task_id)
    if result == "missing":
        abort(404)
    return redirect(url_for("tasks.index"))  # 'ok' and 'already' are both idempotent


@bp.post("/delete/<int:task_id>")
def remove(task_id):
    if not delete(task_id):
        abort(404)
    return redirect(url_for("tasks.index"))
