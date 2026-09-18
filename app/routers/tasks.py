from datetime import date, datetime, timezone
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database.connection import get_db
from app.database.models import Task, TaskStatus
from app.security.auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def list_tasks(request: Request, filter: str = "all", db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    q = db.query(Task).filter(Task.user_id == user.id)
    today = date.today()
    if filter == "today":
        q = q.filter(Task.due_date == today)
    elif filter == "upcoming":
        q = q.filter(Task.due_date > today, Task.status == TaskStatus.pending.value)
    elif filter == "completed":
        q = q.filter(Task.status == TaskStatus.completed.value)
    else:
        q = q.filter(Task.status != TaskStatus.cancelled.value)
    tasks = q.order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).all()
    return templates.TemplateResponse("tasks/index.html", {"request": request, 
        "user": user, "active": "tasks", "tasks": tasks, "filter": filter
    })


@router.post("/create")
async def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("medium"),
    category: str = Form("Other"),
    due_date: str = Form(""),
    due_time: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    dd = None
    if due_date:
        try:
            dd = date.fromisoformat(due_date)
        except ValueError:
            pass
    task = Task(
        user_id=user.id, title=title.strip(), priority=priority, category=category,
        due_date=dd, due_time=due_time or None, description=description.strip() or None
    )
    db.add(task)
    db.commit()
    return RedirectResponse("/tasks", status_code=303)


@router.post("/{task_id}/toggle")
async def toggle_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if task:
        if task.status == TaskStatus.completed.value:
            task.status = TaskStatus.pending.value
            task.completed_at = None
        else:
            task.status = TaskStatus.completed.value
            task.completed_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(request.headers.get("referer", "/tasks"), status_code=303)


@router.post("/{task_id}/delete")
async def delete_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse("/tasks", status_code=303)
