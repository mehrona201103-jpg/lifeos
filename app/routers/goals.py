from datetime import date, datetime, timezone
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database.connection import get_db
from app.database.models import Goal, GoalStatus
from app.security.auth import get_current_user

router = APIRouter(prefix="/goals", tags=["Goals"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def list_goals(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    goals = db.query(Goal).filter(Goal.user_id == user.id).order_by(Goal.created_at.desc()).all()
    today = date.today()
    return templates.TemplateResponse("goals/index.html", {"request": request, 
        "user": user, "active": "goals", "goals": goals, "today": today
    })


@router.post("/create")
async def create_goal(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form("Other"),
    color: str = Form("#7c5cfc"),
    deadline: str = Form(""),
    progress: int = Form(0),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    dl = None
    if deadline:
        try:
            dl = date.fromisoformat(deadline)
        except ValueError:
            pass
    progress = max(0, min(100, progress))
    status = GoalStatus.completed.value if progress >= 100 else GoalStatus.active.value
    goal = Goal(
        user_id=user.id, title=title.strip(), description=description.strip() or None,
        category=category, color=color, deadline=dl, progress=progress, status=status,
        completed_at=datetime.now(timezone.utc) if progress >= 100 else None
    )
    db.add(goal)
    db.commit()
    return RedirectResponse("/goals", status_code=303)


@router.post("/{goal_id}/progress")
async def update_progress(
    goal_id: int, request: Request, progress: int = Form(...), db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal:
        goal.progress = max(0, min(100, progress))
        if goal.progress >= 100:
            goal.status = GoalStatus.completed.value
            goal.completed_at = datetime.now(timezone.utc)
        else:
            goal.status = GoalStatus.active.value
            goal.completed_at = None
        db.commit()
    return RedirectResponse("/goals", status_code=303)


@router.post("/{goal_id}/delete")
async def delete_goal(goal_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user.id).first()
    if goal:
        db.delete(goal)
        db.commit()
    return RedirectResponse("/goals", status_code=303)
