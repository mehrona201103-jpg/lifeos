from datetime import date, datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path

from app.database.connection import get_db
from app.database.models import User, Task, Habit, HabitCompletion, Goal, Transaction, TaskStatus, GoalStatus
from app.security.auth import get_current_user

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def greeting_text(user: User) -> str:
    hour = datetime.now().hour
    name = user.display_name.split()[0] if user.display_name else user.username
    if hour < 12:
        return f"Good morning, {name}"
    elif hour < 18:
        return f"Good afternoon, {name}"
    return f"Good evening, {name}"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    today = date.today()

    # Today's tasks
    today_tasks = db.query(Task).filter(
        Task.user_id == user.id,
        Task.due_date == today,
    ).order_by(Task.priority.desc(), Task.created_at).all()

    # Active habits + completions today
    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.is_active == True).all()
    completed_habit_ids = {
        c.habit_id for c in db.query(HabitCompletion).filter(
            HabitCompletion.user_id == user.id,
            HabitCompletion.completion_date == today,
        ).all()
    }

    # Stats
    tasks_done = db.query(Task).filter(
        Task.user_id == user.id, Task.status == TaskStatus.completed.value,
        func.date(Task.completed_at) == today
    ).count()
    habits_done = len(completed_habit_ids)
    active_goals = db.query(Goal).filter(
        Goal.user_id == user.id, Goal.status == GoalStatus.active.value
    ).count()

    # Finance today
    income_today = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "income",
        Transaction.transaction_date == today
    ).scalar() or 0
    expense_today = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "expense",
        Transaction.transaction_date == today
    ).scalar() or 0

    # Balance (all time for user's currency)
    total_income = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "income"
    ).scalar() or 0
    total_expense = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "expense"
    ).scalar() or 0
    balance = total_income - total_expense

    # Best streak among habits
    best_streak = max((h.current_streak for h in habits), default=0)
    total_habits = len(habits)
    progress = f"{habits_done}/{total_habits}" if total_habits else "0/0"

    return templates.TemplateResponse("dashboard/index.html", {"request": request, 
        "user": user,
        "active": "dashboard",
        "greeting": greeting_text(user),
        "today": today.strftime("%A, %d %B %Y"),
        "streak": best_streak,
        "progress": progress,
        "active_goals": active_goals,
        "balance": balance,
        "currency": user.currency,
        "today_tasks": today_tasks,
        "habits": habits,
        "completed_habit_ids": completed_habit_ids,
        "tasks_done": tasks_done,
        "habits_done": habits_done,
        "income_today": income_today,
        "expense_today": expense_today,
    })
