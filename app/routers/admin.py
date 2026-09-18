from datetime import datetime, timezone
import time
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path

from app.database.connection import get_db, engine
from app.database.models import User, Task, Habit, Goal, Transaction, SocialLink, AdminLog, UserRole
from app.security.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
START = time.time()


def require_admin_user(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user or user.role != UserRole.admin.value:
        return None
    return user


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)

    users_count = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True, User.is_blocked == False).count()
    tasks_count = db.query(Task).count()
    habits_count = db.query(Habit).count()
    goals_count = db.query(Goal).count()
    txs_count = db.query(Transaction).count()
    uptime = round(time.time() - START, 0)

    recent_logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(20).all()

    return templates.TemplateResponse("admin/index.html", {"request": request, 
        "user": admin, "active": "admin",
        "users_count": users_count, "active_users": active_users,
        "tasks_count": tasks_count, "habits_count": habits_count,
        "goals_count": goals_count, "txs_count": txs_count,
        "uptime": uptime, "version": settings.APP_VERSION,
        "db_ok": True, "logs": recent_logs,
    })


@router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: Session = Depends(get_db)):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse("admin/users.html", {"request": request, 
        "user": admin, "active": "admin", "users": users
    })


@router.post("/users/{user_id}/toggle-block")
async def toggle_block(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)
    u = db.query(User).filter(User.id == user_id).first()
    if u and u.role != UserRole.admin.value:
        u.is_blocked = not u.is_blocked
        db.add(AdminLog(admin_id=admin.id, action="toggle_block", details=f"user_id={user_id}"))
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/make-admin")
async def make_admin(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        u.role = UserRole.admin.value
        db.add(AdminLog(admin_id=admin.id, action="make_admin", details=f"user_id={user_id}"))
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/social", response_class=HTMLResponse)
async def social_page(request: Request, db: Session = Depends(get_db)):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)
    links = {s.platform: s for s in db.query(SocialLink).all()}
    return templates.TemplateResponse("admin/social.html", {"request": request, 
        "user": admin, "active": "admin", "links": links
    })


@router.post("/social")
async def save_social(
    request: Request,
    instagram_url: str = Form(""),
    tiktok_url: str = Form(""),
    instagram_enabled: str = Form(""),
    tiktok_enabled: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin_user(request, db)
    if not admin:
        return RedirectResponse("/admin-login", status_code=303)

    for platform, url, enabled in [
        ("instagram", instagram_url.strip(), bool(instagram_enabled)),
        ("tiktok", tiktok_url.strip(), bool(tiktok_enabled)),
    ]:
        link = db.query(SocialLink).filter(SocialLink.platform == platform).first()
        if not link:
            link = SocialLink(platform=platform)
            db.add(link)
        link.url = url or None
        link.is_enabled = enabled and bool(url)
    db.add(AdminLog(admin_id=admin.id, action="update_social_links"))
    db.commit()
    return RedirectResponse("/admin/social", status_code=303)
