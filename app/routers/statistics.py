from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path

from app.database.connection import get_db
from app.database.models import Task, Habit, HabitCompletion, Goal, Transaction, TaskStatus, GoalStatus
from app.security.auth import get_current_user

router = APIRouter(tags=["Statistics"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request, period: int = 30, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    period = period if period in (7, 30, 90, 365) else 30
    start = date.today() - timedelta(days=period)

    tasks_done = db.query(Task).filter(
        Task.user_id == user.id, Task.status == TaskStatus.completed.value
    ).count()
    habits_done = db.query(HabitCompletion).filter(
        HabitCompletion.user_id == user.id, HabitCompletion.completion_date >= start
    ).count()
    active_goals = db.query(Goal).filter(
        Goal.user_id == user.id, Goal.status == GoalStatus.active.value
    ).count()
    completed_goals = db.query(Goal).filter(
        Goal.user_id == user.id, Goal.status == GoalStatus.completed.value
    ).count()

    total_income = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "income",
        Transaction.transaction_date >= start
    ).scalar() or 0
    total_expense = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user.id, Transaction.type == "expense",
        Transaction.transaction_date >= start
    ).scalar() or 0

    # Expense by category
    cats = db.query(Transaction.category, func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == "expense",
        Transaction.transaction_date >= start
    ).group_by(Transaction.category).all()

    # Daily habit completions for chart
    daily = []
    for i in range(min(period, 30)):
        d = date.today() - timedelta(days=min(period, 30) - 1 - i)
        cnt = db.query(HabitCompletion).filter(
            HabitCompletion.user_id == user.id, HabitCompletion.completion_date == d
        ).count()
        daily.append({"date": d.isoformat(), "count": cnt})

    return templates.TemplateResponse("statistics/index.html", {"request": request, 
        "user": user, "active": "statistics", "period": period,
        "tasks_done": tasks_done, "habits_done": habits_done,
        "active_goals": active_goals, "completed_goals": completed_goals,
        "total_income": total_income, "total_expense": total_expense,
        "balance": total_income - total_expense,
        "expense_cats": [{"cat": c, "amount": float(a)} for c, a in cats],
        "daily_habits": daily, "currency": user.currency,
    })


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    today = date.today()
    # Simple activity for last 42 days
    activity = []
    for i in range(41, -1, -1):
        d = today - timedelta(days=i)
        habits = db.query(HabitCompletion).filter(
            HabitCompletion.user_id == user.id, HabitCompletion.completion_date == d
        ).count()
        tasks = db.query(Task).filter(
            Task.user_id == user.id, Task.status == TaskStatus.completed.value,
            func.date(Task.completed_at) == d
        ).count() if hasattr(Task, 'completed_at') else 0
        activity.append({"date": d.isoformat(), "habits": habits, "tasks": tasks, "total": habits + tasks})
    return templates.TemplateResponse("calendar/index.html", {"request": request, 
        "user": user, "active": "calendar", "activity": activity, "today": today.isoformat()
    })
