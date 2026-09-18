from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from app.database.connection import get_db
from app.database.models import User
from app.security.auth import get_current_user, hash_password, verify_password

router = APIRouter(tags=["Profile"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("profile/index.html", {"request": request, 
        "user": user, "active": "profile", "message": None, "error": None
    })


@router.post("/profile")
async def update_profile(
    request: Request,
    display_name: str = Form(...),
    timezone: str = Form("UTC"),
    currency: str = Form("TJS"),
    language: str = Form("en"),
    theme: str = Form("dark"),
    daily_goal: int = Form(5),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    user.display_name = display_name.strip()
    user.timezone = timezone
    user.currency = currency
    user.language = language
    user.theme = theme
    user.daily_goal = max(1, min(50, daily_goal))
    db.commit()
    return templates.TemplateResponse("profile/index.html", {"request": request, 
        "user": user, "active": "profile", "message": "Profile updated", "error": None
    })


@router.post("/profile/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    error = None
    if not verify_password(current_password, user.hashed_password):
        error = "Current password is incorrect"
    elif new_password != confirm_password:
        error = "New passwords do not match"
    elif len(new_password) < 8:
        error = "Password must be at least 8 characters"
    if error:
        return templates.TemplateResponse("profile/index.html", {"request": request, 
            "user": user, "active": "profile", "message": None, "error": error
        })
    user.hashed_password = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse("profile/index.html", {"request": request, 
        "user": user, "active": "profile", "message": "Password changed", "error": None
    })
