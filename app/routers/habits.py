from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database.connection import get_db
from app.database.models import Habit, HabitCompletion
from app.security.auth import get_current_user

router = APIRouter(prefix="/habits", tags=["Habits"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def calc_streak(db: Session, habit: Habit) -> int:
    """Simple daily streak: consecutive days with completion ending today or yesterday."""
    completions = {
        c.completion_date for c in db.query(HabitCompletion).filter(
            HabitCompletion.habit_id == habit.id
        ).all()
    }
    if not completions:
        return 0
    streak = 0
    d = date.today()
    # Allow streak if completed yesterday but not today yet
    if d not in completions:
        d = d - timedelta(days=1)
    while d in completions:
        streak += 1
        d -= timedelta(days=1)
    return streak


@router.get("", response_class=HTMLResponse)
async def list_habits(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    habits = db.query(Habit).filter(Habit.user_id == user.id).order_by(Habit.created_at.desc()).all()
    today = date.today()
    completed = {
        c.habit_id for c in db.query(HabitCompletion).filter(
            HabitCompletion.user_id == user.id, HabitCompletion.completion_date == today
        ).all()
    }
    return templates.TemplateResponse("habits/index.html", {"request": request, 
        "user": user, "active": "habits", "habits": habits, "completed": completed, "today": today
    })


@router.post("/create")
async def create_habit(
    request: Request,
    title: str = Form(...),
    category: str = Form("Other"),
    description: str = Form(""),
    color: str = Form("#7c5cfc"),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    habit = Habit(
        user_id=user.id, title=title.strip(), category=category,
        description=description.strip() or None, color=color
    )
    db.add(habit)
    db.commit()
    return RedirectResponse("/habits", status_code=303)


@router.post("/{habit_id}/toggle")
async def toggle_habit(habit_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not habit:
        return RedirectResponse("/habits", status_code=303)
    today = date.today()
    existing = db.query(HabitCompletion).filter(
        HabitCompletion.habit_id == habit_id, HabitCompletion.completion_date == today
    ).first()
    if existing:
        db.delete(existing)
    else:
        db.add(HabitCompletion(habit_id=habit_id, user_id=user.id, completion_date=today))
    db.commit()
    # Update streak
    habit.current_streak = calc_streak(db, habit)
    if habit.current_streak > habit.best_streak:
        habit.best_streak = habit.current_streak
    db.commit()
    return RedirectResponse(request.headers.get("referer", "/habits"), status_code=303)


@router.post("/{habit_id}/delete")
async def delete_habit(habit_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    habit = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if habit:
        db.delete(habit)
        db.commit()
    return RedirectResponse("/habits", status_code=303)
